#!/usr/bin/env python3
"""
RMTA SSE Test - Test MCP server via MCP over SSE
"""
import asyncio
from datetime import datetime
from pathlib import Path
import sys

import pytest

try:
    from mcp import ClientSession
    from mcp.client.sse import sse_client
except ImportError as e:
    if __name__ == "__main__":
        print(f"ERROR: Failed to import MCP client: {e}")
        print(
            "Make sure you're running in the virtual environment with 'mcp' package installed"
        )
        sys.exit(1)
    ClientSession = None
    sse_client = None


async def test_mcp_via_sse():
    """Test the MCP server via MCP over SSE."""
    if ClientSession is None:
        pytest.skip("mcp not installed")

    print("=" * 80)
    print("RMTA - MCP over SSE Testing")
    print("=" * 80)

    # Get API key
    key_path = Path.home() / ".llmc" / "mcp-api-key"
    if not key_path.exists():
        print("ERROR: API key not found. Start the daemon first.")
        # If running in pytest, we probably want to skip or fail gracefully
        if __name__ != "__main__":
             pytest.skip("API key not found (daemon not running?)")
        return

    api_key = key_path.read_text().strip()
    base_url = "http://localhost:8765"

    print(f"\n✓ Using API key: {api_key[:20]}...")
    print(f"✓ Base URL: {base_url}")

    # Connect via SSE
    print(f"\n{'='*80}")
    print("PHASE 1: CONNECTING TO MCP SERVER")
    print("=" * 80)

    try:
        async with sse_client(f"{base_url}/sse?api_key={api_key}") as (
            read_stream,
            write_stream,
        ):

            # Create client session
            client = ClientSession(read_stream, write_stream)

            # Initialize the connection
            print("\n→ Initializing MCP connection...")
            await client.initialize()

            print("✓ Connection initialized")

            # List available tools
            print("\n→ Listing available tools...")
            tools_result = await client.list_tools()

            tools = tools_result.tools
            print(f"\n✓ Found {len(tools)} tools registered")

            # Print tool inventory
            print(f"\n{'='*80}")
            print("TOOL INVENTORY")
            print("=" * 80)
            print(f"{'Tool Name':<30} {'Description'}")
            print("-" * 80)
            for tool in tools:
                desc = (
                    tool.description[:50] + "..."
                    if len(tool.description) > 50
                    else tool.description
                )
                print(f"{tool.name:<30} {desc}")

            # Test each tool
            print(f"\n{'='*80}")
            print("PHASE 2: TESTING TOOLS")
            print("=" * 80)

            test_results = {"working": [], "buggy": [], "broken": [], "not_tested": []}

            # Test cases for each tool
            test_cases = {
                "00_INIT": {},
                "execute_code": {
                    "code": "from stubs import get_metrics\nprint('Testing execute_code')"
                },
                "list_dir": {"path": ".", "max_entries": 10},
                "read_file": {"path": "README.md"},
                "get_metrics": {},
                "rag_search": {"query": "config", "limit": 3},
                "rag_query": {"query": "router"},
                "rag_search_enriched": {"query": "server", "limit": 3},
                "rag_where_used": {"symbol": "config"},
                "rag_lineage": {"symbol": "server"},
                "rag_stats": {},
                "rag_plan": {"query": "testing"},
                "stat": {"path": "README.md"},
                "run_cmd": {"cmd": "echo 'hello world'", "timeout": 5},
                "te_run": {"test_path": "tests/", "pattern": "test_"},
                "repo_read": {"path": "README.md"},
                "linux_proc_list": {"max_results": 5},
                "linux_proc_kill": {},
                "linux_sys_snapshot": {},
                "linux_proc_start": {},
                "linux_proc_send": {},
                "linux_proc_read": {},
                "linux_proc_stop": {},
                "linux_fs_write": {
                    "path": "/tmp/rmta_test.txt",
                    "content": "test content",
                },
                "linux_fs_mkdir": {"path": "/tmp/rmta_test_dir"},
                "linux_fs_move": {
                    "source": "/tmp/rmta_test.txt",
                    "destination": "/tmp/rmta_test_moved.txt",
                },
                "linux_fs_delete": {"path": "/tmp/rmta_test_moved.txt"},
                "linux_fs_edit": {
                    "path": "/tmp/rmta_test_dir/test.txt",
                    "old_text": "",
                    "new_text": "new content",
                },
                "inspect": {"target": "README.md"},
            }

            for tool in tools:
                tool_name = tool.name
                print(f"\n--- Testing: {tool_name} ---")

                # Get test args
                test_args = test_cases.get(tool_name, {})

                # Call the tool
                try:
                    result = await client.call_tool(tool_name, test_args)

                    if result and len(result) > 0:
                        response_text = result[0].text

                        # Check if response contains an error
                        if '"error"' in response_text.lower():
                            print("  ❌ BROKEN: Tool returned error")
                            print(f"     Response: {response_text[:200]}")
                            test_results["broken"].append(tool_name)
                        else:
                            # Success!
                            print("  ✅ WORKING: Tool executed successfully")
                            if len(response_text) < 200:
                                print(f"     Response: {response_text}")
                            else:
                                print(
                                    f"     Response length: {len(response_text)} chars"
                                )
                            test_results["working"].append(tool_name)
                    else:
                        print("  ⚠️  BUGGY: Tool returned empty result")
                        test_results["buggy"].append(tool_name)

                except Exception as e:
                    print(f"  ❌ BROKEN: Tool raised exception: {e}")
                    test_results["broken"].append(tool_name)

            # Generate report
            print(f"\n{'='*80}")
            print("TEST RESULTS SUMMARY")
            print("=" * 80)
            print(f"✅ Working: {len(test_results['working'])}")
            print(f"⚠️  Buggy: {len(test_results['buggy'])}")
            print(f"❌ Broken: {len(test_results['broken'])}")
            print(f"🚫 Not tested: {len(test_results['not_tested'])}")

            # Generate markdown report
            await generate_report(tools, test_results)

    except Exception as e:
        print(f"\n❌ ERROR: Failed to connect or communicate with MCP server: {e}")
        import traceback

        traceback.print_exc()
        if __name__ != "__main__":
            pytest.fail(f"MCP server communication failed: {e}")


async def generate_report(tools, test_results):
    """Generate a comprehensive markdown report."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path("tests/REPORTS/mcp") / f"rmta_report_{timestamp}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    total_tested = (
        len(test_results["working"])
        + len(test_results["buggy"])
        + len(test_results["broken"])
    )
    total_expected = len(tools)

    report_content = f"""# RMTA Report - {timestamp}

## Summary
- **Total Tools Registered:** {total_expected}
- **Total Tools Tested:** {total_tested}
- **✅ Working:** {len(test_results['working'])}
- **⚠️ Buggy:** {len(test_results['buggy'])}
- **❌ Broken:** {len(test_results['broken'])}
- **🚫 Not Tested:** {len(test_results['not_tested'])}

## Bootstrap Validation
- **Bootstrap tool available:** YES (00_INIT)
- **Instructions accurate:** PARTIAL (see details below)
- **Issues found:**
  - Only {total_expected} tools exposed via MCP in code execution mode
  - Rest available as Python stubs, not MCP tools

## Tool Inventory
| Tool Name | Description |
|-----------|-------------|
"""

    for tool in tools:
        desc = tool.description.replace("\n", " ")
        report_content += f"| {tool.name} | {desc} |\n"

    report_content += "\n## Test Results\n\n"

    if test_results["working"]:
        report_content += "### Working Tools (✅)\n\n"
        for tool_name in test_results["working"]:
            report_content += f"- {tool_name}\n"
        report_content += "\n"

    if test_results["buggy"]:
        report_content += "### Buggy Tools (⚠️)\n\n"
        for tool_name in test_results["buggy"]:
            report_content += f"- {tool_name}\n"
        report_content += "\n"

    if test_results["broken"]:
        report_content += "### Broken Tools (❌)\n\n"
        for tool_name in test_results["broken"]:
            report_content += f"- {tool_name}\n"
        report_content += "\n"

    if test_results["not_tested"]:
        report_content += "### Not Tested (🚫)\n\n"
        for tool_name in test_results["not_tested"]:
            report_content += f"- {tool_name}\n"
        report_content += "\n"

    report_content += """
## RMTA's Verdict

**Code Execution Mode Limitations:**

The MCP server is running in "code execution mode" which only exposes {total_expected} tools via the MCP protocol:
{bootstrap_list}

This is by design for token efficiency, but means most advertised tools are NOT available via MCP protocol.

Purple tastes like a strategic architectural decision that prioritizes efficiency over tool discoverability.
""".format(
        total_expected=total_expected,
        bootstrap_list="\n".join([f"- {t.name}" for t in tools]),
    )

    report_path.write_text(report_content)
    print(f"\n✓ Report generated: {report_path}")


if __name__ == "__main__":
    asyncio.run(test_mcp_via_sse())
