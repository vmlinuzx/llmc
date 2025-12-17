import json
import subprocess
import sys
import threading
import time

# Configuration
SERVER_CMD = [sys.executable, "-m", "llmc_mcp.server"]
LOG_FILE = "tests/REPORTS/mcp/rmta_driver_log.jsonl"


class MCPClient:
    def __init__(self):
        self.process = subprocess.Popen(
            SERVER_CMD,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )
        self.request_id = 0
        self.lock = threading.Lock()
        self.running = True

        # Start stderr reader
        self.stderr_thread = threading.Thread(target=self._read_stderr)
        self.stderr_thread.daemon = True
        self.stderr_thread.start()

    def _read_stderr(self):
        while self.running:
            line = self.process.stderr.readline()
            if not line:
                break
            # print(f"[SERVER LOG] {line.strip()}", file=sys.stderr)

    def send_request(self, method, params=None):
        with self.lock:
            self.request_id += 1
            rid = self.request_id

        payload = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": method,
            "params": params or {},
        }

        json_str = json.dumps(payload)
        try:
            self.process.stdin.write(json_str + "\n")
            self.process.stdin.flush()
        except BrokenPipeError:
            return None

        # Read response
        # In a real client this would be async, here we block for simplicity
        # assuming 1-to-1 request/response for this test driver
        return self._read_response(rid)

    def send_notification(self, method, params=None):
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        json_str = json.dumps(payload)
        try:
            self.process.stdin.write(json_str + "\n")
            self.process.stdin.flush()
        except BrokenPipeError:
            pass

    def _read_response(self, expected_id):
        start_time = time.time()
        while time.time() - start_time < 30:  # 30s timeout
            line = self.process.stdout.readline()
            if not line:
                return None
            try:
                data = json.loads(line)
                if data.get("id") == expected_id:
                    return data
                # Ignore notifications or other IDs (shouldn't happen in strict sequence)
            except json.JSONDecodeError:
                continue
        return {"error": {"message": "Timeout"}}

    def close(self):
        self.running = False
        self.process.terminate()
        self.process.wait()


def run_tests():
    client = MCPClient()
    results = []

    def log_result(category, name, status, details):
        entry = {
            "category": category,
            "name": name,
            "status": status,
            "details": details,
            "timestamp": time.time(),
        }
        results.append(entry)
        print(f"[{status}] {name}: {str(details)[:100]}...")

    try:
        # 1. Initialize
        print("--- Initializing ---")
        init_resp = client.send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "RMTA", "version": "1.0"},
            },
        )

        if not init_resp or "error" in init_resp:
            log_result("Bootstrap", "Protocol Handshake", "❌ Broken", init_resp)
            return results
        else:
            log_result(
                "Bootstrap", "Protocol Handshake", "✅ Works", "Server initialized"
            )

        client.send_notification("notifications/initialized")

        # 2. Discover Tools
        print("--- Listing Tools ---")
        tools_resp = client.send_request("tools/list")
        if not tools_resp or "result" not in tools_resp:
            log_result("Discovery", "List Tools", "❌ Broken", tools_resp)
            return results

        tools = tools_resp["result"].get("tools", [])
        log_result("Discovery", "Tool Count", "✅ Works", f"Found {len(tools)} tools")

        tool_map = {t["name"]: t for t in tools}

        # 3. Test 00_INIT
        print("--- Testing 00_INIT ---")
        if "00_INIT" in tool_map:
            res = client.send_request(
                "tools/call", {"name": "00_INIT", "arguments": {}}
            )
            if res and "result" in res and not res["result"].get("isError"):
                log_result("Bootstrap", "00_INIT", "✅ Works", res["result"])
            else:
                log_result("Bootstrap", "00_INIT", "❌ Broken", res)
        else:
            log_result("Bootstrap", "00_INIT", "❌ Missing", "Tool not found")

        # 4. Systematic Tests
        test_cases = [
            # Basic Info
            ("get_metrics", {}),
            # FS Read
            ("list_dir", {"path": "."}),
            ("stat", {"path": "pyproject.toml"}),
            ("read_file", {"path": "pyproject.toml"}),
            # RAG
            ("rag_search", {"query": "router", "limit": 1}),
            ("rag_plan", {"query": "how to use tools"}),
            # LinuxOps
            ("linux_proc_list", {"max_results": 5}),
            ("linux_sys_snapshot", {}),
            # FS Write (Safe)
            ("linux_fs_mkdir", {"path": ".llmc/tmp/rmta_test", "exist_ok": True}),
            (
                "linux_fs_write",
                {
                    "path": ".llmc/tmp/rmta_test/rmta.txt",
                    "content": "RMTA was here",
                    "mode": "rewrite",
                },
            ),
            ("read_file", {"path": ".llmc/tmp/rmta_test/rmta.txt"}),  # Verify write
            ("linux_fs_delete", {"path": ".llmc/tmp/rmta_test", "recursive": True}),
            # Missing Tool
            ("non_existent_tool", {}),
            # Code Execution Mode
            (
                "execute_code",
                {
                    "code": "from stubs import list_dir\nprint(list_dir(path='.', max_entries=2))"
                },
            ),
        ]

        print("--- Running Systematic Tests ---")
        for name, args in test_cases:
            if name not in tool_map and name != "non_existent_tool":
                # Special case: execute_code might be available only in code_exec mode
                # But we are iterating over a fixed list.
                log_result("Test", name, "🚫 Not Tested", "Tool not available")
                continue

            print(f"Testing {name}...")
            res = client.send_request("tools/call", {"name": name, "arguments": args})

            status = "✅ Works"
            details = ""

            if not res:
                status = "❌ Broken"
                details = "No response"
            elif "error" in res:
                # Protocol error
                if name == "non_existent_tool":
                    status = "✅ Works"  # Expected error
                    details = "Correctly reported unknown tool"
                else:
                    status = "❌ Broken"
                    details = res["error"]
            elif res.get("result", {}).get("isError"):
                # Tool execution error
                status = "⚠️ Buggy"  # Or broken depending on severity
                details = res["result"]

                # Check content for "error" JSON
                content = res["result"].get("content", [])
                if content:
                    text = content[0].get("text", "")
                    if '"error"' in text:
                        # It returned a JSON error object, which is a handled failure
                        pass
            else:
                # Success
                details = res["result"]
                # content verification
                content = res["result"].get("content", [])
                if content and isinstance(content, list) and len(content) > 0:
                    text = content[0].get("text", "")
                    # Only flag if top-level error key exists in JSON
                    if '{"error":' in text and '"error": null' not in text:
                        status = "⚠️ Buggy"  # Tool said success but returned error json

            log_result("Test", name, status, details)

    except Exception as e:
        log_result("System", "Driver", "❌ Crashed", str(e))
    finally:
        client.close()

    # Save results
    with open(LOG_FILE, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print(f"\nResults saved to {LOG_FILE}")


if __name__ == "__main__":
    run_tests()
