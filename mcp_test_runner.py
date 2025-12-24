
import sys
import json
import subprocess
import os
import time

def write_message(process, message):
    message_str = json.dumps(message)
    print(f"SENDING: {message_str}", file=sys.stderr)
    if process.stdin:
        process.stdin.write(message_str + '\n')
        process.stdin.flush()

def read_message(process, expected_id):
    while process.poll() is None:
        line = process.stdout.readline()
        if not line:
            return None, "No output from server"
        print(f"RECEIVED: {line.strip()}", file=sys.stderr)
        try:
            message = json.loads(line)
            if 'id' in message and message['id'] == expected_id:
                return message, line
        except json.JSONDecodeError:
            print(f"WARNING: Could not decode JSON: {line.strip()}", file=sys.stderr)
            pass
    return None, "Process exited"


def main():
    if len(sys.argv) < 2:
        print("Usage: python mcp_test_runner.py <tool_name> [tool_args_json]")
        sys.exit(1)

    tool_name = sys.argv[1]
    tool_args_str = sys.argv[2] if len(sys.argv) > 2 else '{}'
    tool_args = json.loads(tool_args_str)

    env = os.environ.copy()
    env["LLMC_ISOLATED"] = "1"

    stderr_log_path = "/home/vmlinux/.gemini/tmp/374224a11efb3b264acdde863d43231b170786efcc9917b056946c0602063280/mcp_server_stderr.log"
    with open(stderr_log_path, 'w') as stderr_log:
        server_process = subprocess.Popen(
            ['python3', '-m', 'llmc_mcp.server'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_log,
            text=True,
            bufsize=1,
            preexec_fn=os.setsid,
            env=env
        )
        
        print("Waiting for server to start...", file=sys.stderr)
        time.sleep(2)
        print("Server should be started.", file=sys.stderr)

        init_request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "1",
                "capabilities": {},
                "clientInfo": {
                    "name": "MCP-Test-Runner",
                    "version": "0.1.0"
                }
            },
            "id": 0
        }
        
        write_message(server_process, init_request)
        init_response, init_response_str = read_message(server_process, 0)

        if init_response:
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            }
            write_message(server_process, initialized_notification)

        tool_call_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": tool_args
            },
            "id": 1
        }
        write_message(server_process, tool_call_request)
        tool_response, tool_response_str = read_message(server_process, 1)
        
        print("--- INIT RESPONSE ---")
        print(init_response_str)
        print("--- TOOL RESPONSE ---")
        print(tool_response_str)

        if server_process.poll() is None:
            try:
                os.killpg(os.getpgid(server_process.pid), 15)
            except ProcessLookupError:
                pass
    
    print(f"Server stderr logged to {stderr_log_path}")

if __name__ == "__main__":
    main()

