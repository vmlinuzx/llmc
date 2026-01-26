import asyncio
from datetime import datetime
import json
import os
import sys
from typing import Any

# Configuration
# Use the .venv python explicitly
VENV_PYTHON = os.path.abspath(".venv/bin/python")
SERVER_CMD = [VENV_PYTHON, "-m", "llmc_mcp.server"]
REPORT_JSON = "tests/rmta_test_results.json"


class MCPClient:
    def __init__(self):
        self.process = None
        self.request_id = 0
        self.pending_requests = {}

    async def start(self):
        env = os.environ.copy()
        # Ensure we use the venv python
        self.process = await asyncio.create_subprocess_exec(
            *SERVER_CMD,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        # Start reader tasks
        asyncio.create_task(self._read_loop())
        asyncio.create_task(self._stderr_loop())

    async def _stderr_loop(self):
        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                # Print stderr to console for debugging
                print(f"[SERVER STDERR] {line.decode().strip()}", file=sys.stderr)
        except Exception:
            pass

    async def _read_loop(self):
        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break

                try:
                    message = json.loads(line.decode())
                    if "id" in message and message["id"] in self.pending_requests:
                        future = self.pending_requests.pop(message["id"])
                        if "error" in message:
                            future.set_exception(
                                Exception(f"RPC Error: {message['error']}")
                            )
                        else:
                            future.set_result(message.get("result"))
                except json.JSONDecodeError:
                    print(f"Invalid JSON received: {line}", file=sys.stderr)

        except Exception as e:
            print(f"Reader loop error: {e}", file=sys.stderr)

    async def send_request(self, method: str, params: dict | None = None) -> Any:
        self.request_id += 1
        req_id = self.request_id
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }

        # NDJSON: Just the JSON + newline
        body = json.dumps(request).encode() + b"\n"

        future = asyncio.get_running_loop().create_future()
        self.pending_requests[req_id] = future

        self.process.stdin.write(body)
        await self.process.stdin.drain()

        try:
            return await asyncio.wait_for(future, timeout=30.0)
        except TimeoutError:
            del self.pending_requests[req_id]
            raise Exception(f"Timeout waiting for {method}") from None

    async def send_notification(self, method: str, params: dict | None = None):
        request = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        body = json.dumps(request).encode() + b"\n"
        self.process.stdin.write(body)
        await self.process.stdin.drain()

    async def stop(self):
        if self.process:
            self.process.terminate()
            try:
                await self.process.wait()
            except Exception:
                pass


async def run_tests():
    client = MCPClient()
    results = {
        "timestamp": datetime.now().isoformat(),
        "tools_discovered": [],
        "tests": [],
    }

    try:
        print("Starting Server...")
        await client.start()

        # 1. Initialize
        print("Initializing...")
        init_result = await client.send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "RMTA", "version": "1.0"},
            },
        )
        await client.send_notification("notifications/initialized")
        results["server_info"] = init_result.get("serverInfo")

        # 2. List Tools
        print("Listing Tools...")
        tools_response = await client.send_request("tools/list")
        tools = tools_response.get("tools", [])
        results["tools_discovered"] = tools
        print(f"Discovered {len(tools)} tools")

        tool_map = {t["name"]: t for t in tools}

        # 3. Systematic Testing
        test_cases = [
            # Bootstrap
            {"tool": "00_INIT", "args": {}, "desc": "Bootstrap check"},
            # Core FS
            {"tool": "read_file", "args": {"path": "README.md"}, "desc": "Read README"},
            {"tool": "list_dir", "args": {"path": "."}, "desc": "List root"},
            {"tool": "stat", "args": {"path": "pyproject.toml"}, "desc": "Stat config"},
            # RAG
            {
                "tool": "rag_search",
                "args": {"query": "routing", "limit": 1},
                "desc": "RAG Search",
            },
            {
                "tool": "rag_plan",
                "args": {"query": "how does routing work"},
                "desc": "RAG Plan",
            },
            # Metrics
            {"tool": "get_metrics", "args": {}, "desc": "Get Metrics"},
            # Linux Ops
            {
                "tool": "linux_proc_list",
                "args": {"max_results": 5},
                "desc": "List Processes",
            },
            {"tool": "linux_sys_snapshot", "args": {}, "desc": "Sys Snapshot"},
            # Broken/Missing checks (Intentional Failures)
            {
                "tool": "non_existent_tool",
                "args": {},
                "desc": "Missing Tool Check",
                "expect_error": True,
            },
            # FS Write (Test Safety)
            {
                "tool": "linux_fs_mkdir",
                "args": {"path": "rmta_test_dir"},
                "desc": "Mkdir",
                "expected_missing": True,
            },
            {
                "tool": "linux_fs_write",
                "args": {"path": "rmta_test_dir/test.txt", "content": "Hello"},
                "desc": "Write File",
                "expected_missing": True,
            },
            # Execute Code Tests (The Real Meat)
            {
                "tool": "execute_code",
                "args": {
                    "code": "from stubs import rag_search; import json; print(json.dumps(rag_search(query='router', limit=1)))"
                },
                "desc": "Exec: RAG Search",
            },
            {
                "tool": "execute_code",
                "args": {
                    "code": "from stubs import stat; import json; print(json.dumps(stat(path='pyproject.toml')))"
                },
                "desc": "Exec: Stat",
            },
            {
                "tool": "execute_code",
                "args": {
                    "code": "from stubs import linux_proc_list; import json; print(json.dumps(linux_proc_list(max_results=1)))"
                },
                "desc": "Exec: Proc List",
            },
        ]

        for test in test_cases:
            tool_name = test["tool"]
            print(f"Testing {tool_name}...")

            test_result = {
                "tool": tool_name,
                "description": test["desc"],
                "status": "pending",
                "input": test["args"],
            }

            # Check availability
            if tool_name not in tool_map and not test.get("expect_error"):
                if test.get("expected_missing"):
                    test_result["status"] = "missing (expected)"
                    results["tests"].append(test_result)
                    continue
                else:
                    test_result["status"] = "missing"
                    test_result["error"] = "Tool not found in discovery list"
                    results["tests"].append(test_result)
                    continue

            try:
                if tool_name == "non_existent_tool":
                    # Verify handling of unknown tools
                    try:
                        await client.send_request(
                            "tools/call", {"name": tool_name, "arguments": test["args"]}
                        )
                        test_result["status"] = "failed"  # Should have failed
                        test_result["error"] = "Server did not reject unknown tool"
                    except Exception as e:
                        test_result["status"] = "passed"  # Correctly rejected
                        test_result["response"] = str(e)
                else:
                    response = await client.send_request(
                        "tools/call", {"name": tool_name, "arguments": test["args"]}
                    )

                    # MCP returns content list
                    content = response.get("content", [])
                    text_content = content[0].get("text", "") if content else ""

                    # Check for embedded errors in successful responses (soft errors)
                    is_soft_error = False
                    try:
                        parsed = json.loads(text_content)
                        if isinstance(parsed, dict) and "error" in parsed:
                            is_soft_error = True
                            test_result["error"] = parsed["error"]
                    except Exception:
                        pass

                    test_result["response"] = text_content

                    if is_soft_error:
                        test_result["status"] = (
                            "buggy"  # Or broken depending on severity
                        )
                    else:
                        test_result["status"] = "passed"

            except Exception as e:
                test_result["status"] = "error"
                test_result["error"] = str(e)

            results["tests"].append(test_result)

    except Exception as e:
        results["fatal_error"] = str(e)
        print(f"Fatal Error: {e}")
    finally:
        await client.stop()

    with open(REPORT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results written to {REPORT_JSON}")


if __name__ == "__main__":
    asyncio.run(run_tests())
