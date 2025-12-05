import subprocess
import json
import sys
import os
import time
from typing import Any, Dict, List, Optional

class MCPClient:
    def __init__(self):
        self.process = None
        self.request_id = 0

    def start(self):
        env = os.environ.copy()
        # Ensure we are using the python from the current environment
        self.process = subprocess.Popen(
            [sys.executable, "-m", "llmc_mcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            env=env,
            bufsize=0 # Unbuffered
        )
    
    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()

    def send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        req_id = self.request_id
        self.request_id += 1
        
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params
            
        json_req = json.dumps(request)
        # print(f"SEND: {json_req}", file=sys.stderr)
        self.process.stdin.write(json_req + "\n")
        self.process.stdin.flush()
        
        return self.read_response(req_id)

    def send_notification(self, method: str, params: Optional[Dict] = None):
        request = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            request["params"] = params
            
        json_req = json.dumps(request)
        # print(f"NOTIFY: {json_req}", file=sys.stderr)
        self.process.stdin.write(json_req + "\n")
        self.process.stdin.flush()

    def read_response(self, expected_id: int) -> Dict:
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise Exception("Server closed connection")
            
            # print(f"RECV: {line.strip()}", file=sys.stderr)
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue # Skip non-json lines (logs?)
            
            if "id" in msg and msg["id"] == expected_id:
                return msg
            # Ignore other messages/notifications for now

    def call_tool(self, name: str, arguments: Dict) -> Dict:
        return self.send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })

def run_tests():
    client = MCPClient()
    report = {
        "summary": {"total": 0, "working": 0, "buggy": 0, "broken": 0, "not_tested": 0},
        "tools": [],
        "results": [],
        "incidents": []
    }
    
    try:
        print("Starting MCP Server...")
        client.start()
        
        # Initialize
        print("Initializing...")
        init_res = client.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "RMTA", "version": "1.0"}
        })
        
        if "error" in init_res:
            print(f"FATAL: Initialization failed: {init_res['error']}")
            return
            
        client.send_notification("notifications/initialized")
        
        # List Tools
        print("Listing tools...")
        tools_res = client.send_request("tools/list")
        if "error" in tools_res:
            print(f"FATAL: tools/list failed: {tools_res['error']}")
            return
            
        tools = tools_res["result"]["tools"]
        
        # Discover Stubs if in code execution mode
        stubs = []
        stubs_dir = ".llmc/stubs"
        if os.path.exists(stubs_dir):
            print(f"Checking stubs in {stubs_dir}...")
            for f in os.listdir(stubs_dir):
                if f.endswith(".py") and f != "__init__.py":
                    stubs.append({"name": f[:-3], "description": "Stubbed tool (via execute_code)", "is_stub": True})
        
        all_tools = tools + stubs
        report["tools"] = all_tools
        report["summary"]["total"] = len(all_tools)
        
        print(f"Discovered {len(tools)} MCP tools and {len(stubs)} stubs.")
        
        # Test Loop
        for tool in all_tools:
            name = tool["name"]
            description = tool.get("description", "")
            is_stub = tool.get("is_stub", False)
            print(f"\nTesting tool: {name} {'(Stub)' if is_stub else ''}")
            
            result_entry = {"name": name, "status": "UNKNOWN", "notes": ""}
            
            if is_stub:
                # For stubs, we test via execute_code
                if not any(t['name'] == 'execute_code' for t in tools):
                     result_entry["status"] = "🚫 Not Tested"
                     result_entry["notes"] = "Stub requires execute_code tool"
                     report["summary"]["not_tested"] += 1
                     report["results"].append(result_entry)
                     continue
                
                # Construct a test snippet
                # 00_INIT says: from stubs import <tool_name>
                
                code_snippet = ""
                if name == "rag_query":
                    code_snippet = "from stubs import rag_query\nprint(rag_query(query='routing'))"
                elif name == "run_cmd":
                    code_snippet = "from stubs import run_cmd\nprint(run_cmd(command='echo stub_test'))"
                elif name == "read_file":
                    code_snippet = "from stubs import read_file\nprint(read_file(path='README.md'))"
                elif name == "list_dir":
                     code_snippet = "from stubs import list_dir\nprint(list_dir(path='.'))"
                else:
                    # Generic import test
                    code_snippet = f"from stubs import {name}\nprint('{name} imported')"

                # Execute
                start_time = time.time()
                call_res = client.call_tool("execute_code", {"code": code_snippet})
                duration = time.time() - start_time

                if "error" in call_res:
                    result_entry["status"] = "❌ Broken"
                    result_entry["notes"] = f"execute_code failed: {call_res['error'].get('message')}"
                    report["summary"]["broken"] += 1
                else:
                    content = call_res.get("result", {}).get("content", [])
                    is_error = call_res.get("result", {}).get("isError", False)
                    text_out = "".join([c["text"] for c in content if c["type"] == "text"])
                    
                    if is_error: # Python runtime error
                        result_entry["status"] = "❌ Broken" 
                        result_entry["notes"] = f"Python error: {text_out.strip()[:100]}"
                        report["summary"]["broken"] += 1
                    elif "ImportError" in text_out:
                         result_entry["status"] = "❌ Broken"
                         result_entry["notes"] = f"Import failed: {text_out.strip()[:100]}"
                         report["summary"]["broken"] += 1
                    else:
                        result_entry["status"] = "✅ Working"
                        result_entry["notes"] = f"Stub execution success. Output: {text_out.strip()[:50]}..."
                        report["summary"]["working"] += 1

                report["results"].append(result_entry)
                print(f"  -> {result_entry['status']}")
                continue

            try:
                # Define test cases based on tool name
                args = {}
                if name == "00_INIT":
                    args = {} 
                elif name == "rag_search":
                    args = {"query": "routing"}
                elif name == "read_file":
                    args = {"path": "README.md"}
                elif name == "list_dir":
                    args = {"path": "."}
                elif name == "stat":
                    args = {"path": "pyproject.toml"}
                elif name == "run_cmd":
                    args = {"command": "echo 'hello'"}
                elif name == "execute_code":
                    args = {"code": "print('Hello from execute_code')"}
                elif name == "get_metrics":
                    args = {}
                elif name == "linux_proc_list":
                    args = {}
                elif name == "linux_sys_snapshot":
                    args = {}
                else:
                    result_entry["status"] = "🚫 Not Tested"
                    result_entry["notes"] = "No automated test case defined"
                    report["summary"]["not_tested"] += 1
                    report["results"].append(result_entry)
                    continue

                # Execute
                start_time = time.time()
                call_res = client.call_tool(name, args)
                duration = time.time() - start_time
                
                if "error" in call_res:
                    result_entry["status"] = "❌ Broken"
                    result_entry["notes"] = f"Error: {call_res['error'].get('message')}"
                    report["summary"]["broken"] += 1
                    
                    report["incidents"].append({
                        "tool": name,
                        "severity": "P1",
                        "status": "BROKEN",
                        "tried": f"Called {name} with {args}",
                        "expected": "Success response",
                        "actual": str(call_res['error']),
                        "recommendation": "Check server logs and handler implementation"
                    })
                else:
                    content = call_res.get("result", {}).get("content", [])
                    is_error = call_res.get("result", {}).get("isError", False)
                    
                    # Special check for 00_INIT content
                    if name == "00_INIT":
                         text_content = "".join([c["text"] for c in content if c["type"] == "text"])
                         print(f"--- 00_INIT CONTENT ---\n{text_content}\n-----------------------")
                    
                    if is_error:
                         result_entry["status"] = "❌ Broken"
                         result_entry["notes"] = f"Tool returned isError=True. Content: {str(content)[:100]}..."
                         report["summary"]["broken"] += 1
                    else:
                        result_entry["status"] = "✅ Working"
                        result_entry["notes"] = f"Success. Duration: {duration:.2f}s. Content len: {len(str(content))}"
                        report["summary"]["working"] += 1

            except Exception as e:
                result_entry["status"] = "❌ Broken"
                result_entry["notes"] = f"Exception during test: {str(e)}"
                report["summary"]["broken"] += 1
            
            report["results"].append(result_entry)
            print(f"  -> {result_entry['status']}")

    except Exception as e:
        print(f"FATAL: Harness crashed: {e}")
    finally:
        client.stop()
        
    # Generate Markdown Report
    generate_report(report)

def generate_report(data):
    ts = time.strftime("%Y%m%d_%H%M%S")
    filename = f"tests/REPORTS/mcp/rmta_gemini_report_{ts}.md"
    
    md = f"# RMTA Gemini Report - {ts}\n\n## Summary\n- **Total Tools Tested:** {data['summary']['total']}\n- **✅ Working:** {data['summary']['working']}\n- **⚠️ Buggy:** {data['summary']['buggy']}\n- **❌ Broken:** {data['summary']['broken']}\n- **🚫 Not Tested:** {data['summary']['not_tested']}\n\n## Bootstrap Validation\n- Bootstrap tool available: {'YES' if any(t['name'] == '00_INIT' for t in data['tools']) else 'NO'}\n- Instructions accurate: UNKNOWN (Automated check)\n\n## Tool Inventory\n| Name | Description |\n|------|-------------|\n"
    for tool in data['tools']:
        desc = tool.get('description', 'No description').replace('\n', ' ')[:100]
        md += f"| `{tool['name']}` | {desc} |\n"

    md += "\n## Test Results\n\n"
    
    # Group by status
    status_map = {
        "✅ Working": [],
        "⚠️ Buggy": [],
        "❌ Broken": [],
        "🚫 Not Tested": [],
        "UNKNOWN": []
    }
    
    for res in data['results']:
        status_map.get(res['status'], status_map["UNKNOWN"]).append(res)
        
    for status, items in status_map.items():
        if not items: continue
        md += f"### {status}\n"
        for item in items:
            md += f"- **{item['name']}**: {item['notes']}\n"
        md += "\n"

    md += "## Incidents\n"
    if not data['incidents']:
        md += "No incidents logged.\n"
    else:
        for inc in data['incidents']:
            md += f"### {inc['tool']} - {inc['status']}\n"
            md += f"**Severity:** {inc['severity']}\n"
            md += f"**Tried:** {inc['tried']}\n"
            md += f"**Actual:** {inc['actual']}\n"
            md += f"**Recommendation:** {inc['recommendation']}\n\n"

    md += "\n## RMTA's Verdict\nAutomated test completed.\n"
    
    with open(filename, "w") as f:
        f.write(md)
    print(f"Report generated: {filename}")

if __name__ == "__main__":
    run_tests()
