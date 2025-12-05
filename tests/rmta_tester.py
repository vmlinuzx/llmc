import sys
import os
import json
import asyncio
from pathlib import Path

# Add repo root to path
sys.path.insert(0, os.getcwd())

try:
    from llmc_mcp.server import LlmcMcpServer
    from llmc_mcp.config import load_config
except ImportError as e:
    print(f"Failed to import llmc_mcp: {e}")
    sys.exit(1)

async def main():
    print("--- RMTA TESTER STARTED ---")
    
    # 1. Load Config
    try:
        config = load_config()
        print(f"Config loaded. Mode: {'Code Execution' if config.code_execution.enabled else 'Classic'}")
    except Exception as e:
        print(f"Failed to load config: {e}")
        sys.exit(1)

    # 2. Initialize Server
    try:
        server = LlmcMcpServer(config)
        print("Server initialized successfully.")
    except Exception as e:
        print(f"Server initialization failed: {e}")
        sys.exit(1)

    # 3. Inventory Tools
    tools = server.tools
    print(f"\n--- Tool Inventory ({len(tools)} tools) ---")
    tool_names = [t.name for t in tools]
    for t in tools:
        print(f"- {t.name}")
    
    # 4. Bootstrap Test
    if "00_INIT" in tool_names:
        print("\n--- Testing 00_INIT ---")
        try:
            res = await server._handle_bootstrap({})
            print("00_INIT Result: ✅ OK")
        except Exception as e:
            print(f"00_INIT Failed: ❌ {e}")
    else:
        print("\n00_INIT NOT FOUND in tool list.")

    # 5. Execute Code Tests (if in code exec mode)
    if config.code_execution.enabled and "execute_code" in tool_names:
        print("\n--- Testing execute_code ---")
        
        test_cases = [
            ("RAG Search", "from stubs import rag_search; print(rag_search(query='config'))"),
            ("Read File", "from stubs import read_file; print(read_file(path='README.md'))"),
            ("Proc List", "from stubs import linux_proc_list; print(linux_proc_list(max_results=2))"),
            ("System Snapshot", "from stubs import linux_sys_snapshot; print(linux_sys_snapshot())"),
            ("Metric Check", "from stubs import get_metrics; print(get_metrics())"),
            ("FS Write", "from stubs import linux_fs_write; print(linux_fs_write(path='tests/rmta_artifact.txt', content='RMTA was here'))"),
            ("Run Cmd LS", "from stubs import run_cmd; print(run_cmd(command='ls -la tests/'))"),
            ("Run Cmd Forbidden", "from stubs import run_cmd; print(run_cmd(command='rm -rf /'))"),
            # Intentional Fail
            ("Bad Tool", "from stubs import fake_tool; print(fake_tool())") 
        ]

        for name, code in test_cases:
            print(f"\nTest: {name}")
            try:
                # Call the handler directly
                res = await server._handle_execute_code({"code": code})
                output = res[0].text
                
                try:
                    parsed = json.loads(output)
                    if parsed.get("success"):
                         print(f"✅ Passed. Stdout len: {len(parsed.get('stdout', ''))}")
                         # print(f"Debug Out: {parsed.get('stdout')[:200]}")
                    else:
                         err = parsed.get('error') or parsed.get('stderr')
                         if name == "Bad Tool":
                             print(f"✅ Correctly Failed (Expected): {err}")
                         elif name == "Run Cmd Forbidden":
                              print(f"✅ Correctly Blocked (Expected): {err}")
                         else:
                             print(f"❌ Failed. Error: {err}")
                except json.JSONDecodeError:
                    print(f"⚠️  Non-JSON output: {output[:100]}")

            except Exception as e:
                print(f"❌ Exception: {e}")

    # 6. List Stubs
    if config.code_execution.enabled:
        stubs_dir = Path(config.code_execution.stubs_dir)
        if stubs_dir.exists():
             stubs = [f.name for f in stubs_dir.glob("*.py") if f.name != "__init__.py"]
             print(f"\n--- Generated Stubs ({len(stubs)}) ---")
             print(", ".join(sorted(stubs)))

    print("\n--- RMTA TESTER FINISHED ---")

if __name__ == "__main__":
    asyncio.run(main())
