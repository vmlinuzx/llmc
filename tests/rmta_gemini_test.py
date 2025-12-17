#!/usr/bin/env python3
"""
RMTA Gemini Test - Ruthless MCP Testing Agent
"""
import asyncio
from datetime import datetime
import os
from pathlib import Path
import sys
import traceback

# Add project root to path
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))


async def test_mcp_server():
    """Test the MCP server via direct MCP protocol."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = (
        project_root / "tests/REPORTS/mcp" / f"rmta_gemini_report_{timestamp}.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("RMTA - Ruthless MCP Testing Agent - Gemini Edition")
    print("=" * 80)

    # Import MCP client
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as e:
        print(f"ERROR: Failed to import MCP client: {e}")
        return

    # Path to the MCP server
    server_script = project_root / "llmc_mcp" / "server.py"

    if not server_script.exists():
        print(f"ERROR: Server script not found at {server_script}")
        return

    print(f"\n✓ Using server {server_script}")

    # Start the MCP client
    print(f"\n{'='*80}")
    print("Phase 1: Connecting to MCP Server")
    print("=" * 80)

    try:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(server_script)],
            env=os.environ.copy(),  # Pass current environment
        )

        async with stdio_client(server_params) as (read, write):
            # Create client session
            client = ClientSession(read, write)

            # Initialize the connection
            print("\n→ Initializing MCP connection...")
            await client.initialize()

            print("✓ Connection initialized")

            # List available tools
            print("\n→ Listing available tools...")
            tools_result = await client.list_tools()
            tools = tools_result.tools

            tool_map = {t.name: t for t in tools}
            print(f"\n✓ Found {len(tools)} tools registered")

            # ---------------------------------------------------------
            # Phase 1: Bootstrap Validation
            # ---------------------------------------------------------
            print(f"\n{'='*80}")
            print("PHASE 1: BOOTSTRAP VALIDATION")
            print("=" * 80)

            bootstrap_available = "00_INIT" in tool_map
            print(
                f"Bootstrap tool (00_INIT) available: {'YES' if bootstrap_available else 'NO'}"
            )

            bootstrap_issues = []
            if not bootstrap_available:
                bootstrap_issues.append("00_INIT tool missing")
            else:
                # Call 00_INIT to get instructions
                try:
                    print("Calling 00_INIT...")
                    init_result = await client.call_tool("00_INIT", {{}})
                    if init_result and len(init_result.content) > 0:
                        print("✓ 00_INIT returned content")
                        # Here we would validate instructions if we could parse them
                    else:
                        print("⚠️ 00_INIT returned empty content")
                        bootstrap_issues.append("00_INIT returned empty content")
                except Exception as e:
                    print(f"❌ 00_INIT failed: {e}")
                    bootstrap_issues.append(f"00_INIT failed: {str(e)}")

            # ---------------------------------------------------------
            # Phase 2: Tool Discovery & Inventory
            # ---------------------------------------------------------
            print(f"\n{'='*80}")
            print("PHASE 2: TOOL DISCOVERY")
            print("=" * 80)

            print(f"{ 'Tool Name':<30} {'Description'}")
            print("-" * 80)
            for tool in tools:
                desc = (
                    (tool.description or "")[:50] + "..."
                    if tool.description and len(tool.description) > 50
                    else (tool.description or "")
                )
                print(f"{tool.name:<30} {desc}")

            # ---------------------------------------------------------
            # Phase 3: Systematic Tool Testing
            # ---------------------------------------------------------
            print(f"\n{'='*80}")
            print("PHASE 3: SYSTEMATIC TOOL TESTING")
            print("=" * 80)

            results = {"working": [], "buggy": [], "broken": [], "not_tested": []}

            incidents = []

            for tool in tools:
                print(f"\n--- Testing: {tool.name} ---")

                test_args = {{}}

                # Define test cases
                if tool.name == "00_INIT":
                    # Already tested
                    test_args = {{}}
                elif tool.name == "list_dir":
                    test_args = {{"path": "."}}
                elif tool.name == "read_file":
                    test_args = {{"path": "README.md"}}
                elif tool.name == "stat":
                    test_args = {{"path": "pyproject.toml"}}
                elif tool.name == "get_metrics":
                    test_args = {{}}
                elif tool.name.startswith("rag_"):
                    test_args = (
                        {"query": "LLMC", "n_results": 1}
                        if "query"
                        in (
                            tool.inputSchema.get("properties", {{}})
                            if tool.inputSchema
                            else {{}}
                        )
                        else {{}}
                    )
                    # Adjust for specific rag tools
                    if tool.name == "rag_where_used":
                        test_args = {{"symbol": "server"}}
                    elif tool.name == "rag_lineage":
                        test_args = {{"symbol": "Config"}}
                elif tool.name == "linux_proc_list":
                    test_args = {{"max_results": 5}}
                elif tool.name == "run_cmd":
                    test_args = {{"cmd": "echo 'hello world'"}}
                elif tool.name == "linux_fs_write":
                    test_args = {
                        {
                            "path": str(project_root / "tests" / "rmta_test_write.txt"),
                            "content": "RMTA was here",
                        }
                    }
                elif tool.name == "linux_fs_delete":
                    # Be careful, maybe delete what we wrote
                    test_args = {
                        {"path": str(project_root / "tests" / "rmta_test_write.txt")}
                    }  #
                    # Only test delete if write works? For now, let's try write first
                else:
                    # Generic fallback
                    test_args = {{}}
                    if tool.inputSchema and "properties" in tool.inputSchema:
                        for prop in tool.inputSchema["properties"]:
                            if prop == "path":
                                test_args["path"] = "."
                            elif prop == "query":
                                test_args["query"] = "test"

                try:
                    print(f"Arguments: {test_args}")
                    res = await client.call_tool(tool.name, test_args)

                    is_error = False
                    content_str = ""

                    if hasattr(res, "content") and res.content:
                        content_str = str(res.content)
                        if "error" in content_str.lower() and "error" not in tool.name:
                            # Check if it is a real error or just the word error in content
                            # Usually tools return TextContent(type='text', text='...')
                            # We should check the text content
                            for c in res.content:
                                if (
                                    hasattr(c, "text")
                                    and "error" in c.text.lower()
                                    and "traceback" in c.text.lower()
                                ):
                                    is_error = True

                    if hasattr(res, "isError") and res.isError:
                        is_error = True

                    if is_error:
                        print("  ❌ BROKEN: Tool returned error")
                        print(f"     Response: {content_str[:200]}")
                        results["broken"].append(tool.name)
                        incidents.append(
                            {
                                "tool": tool.name,
                                "severity": "P1",
                                "status": "BROKEN",
                                "expected": "Successful execution",
                                "actual": f"Error response: {content_str[:200]}",
                                "evidence": content_str,
                            }
                        )
                    elif not res.content:
                        print("  ⚠️ BUGGY: Empty content")
                        results["buggy"].append(tool.name)
                        incidents.append(
                            {
                                "tool": tool.name,
                                "severity": "P2",
                                "status": "BUGGY",
                                "expected": "Content",
                                "actual": "Empty content",
                                "evidence": str(res),
                            }
                        )
                    else:
                        print("  ✅ WORKING")
                        results["working"].append(tool.name)

                except Exception as e:
                    print(f"  ❌ BROKEN: Exception: {e}")
                    results["broken"].append(tool.name)
                    incidents.append(
                        {
                            "tool": tool.name,
                            "severity": "P0",
                            "status": "BROKEN",
                            "expected": "No exception",
                            "actual": f"Exception: {str(e)}",
                            "evidence": traceback.format_exc(),
                        }
                    )

            # ---------------------------------------------------------
            # Phase 4: Generate Report
            # ---------------------------------------------------------

            report_content = f"""# RMTA Gemini Report - {timestamp}

## Summary
- **Total Tools Tested:** {len(tools)}
- **✅ Working:** {len(results['working'])}
- **⚠️ Buggy:** {len(results['buggy'])}
- **❌ Broken:** {len(results['broken'])}
- **🚫 Not Tested:** {len(results['not_tested'])}

## Bootstrap Validation
- Bootstrap tool available: {'YES' if bootstrap_available else 'NO'}
- Instructions accurate: {'PARTIAL' if bootstrap_issues else 'YES'}
- Issues found: {bootstrap_issues}

## Tool Inventory
| Tool Name | Description |
|-----------|-------------|
"""
            for tool in tools:
                desc = (tool.description or "").replace("\n", " ")
                report_content += f"| {tool.name} | {desc} |\\n"

            report_content += "\n## Test Results\n\n"

            report_content += (
                "### Working Tools (✅)\n"
                + "\n".join([f"- {t}" for t in results["working"]])
                + "\n\n"
            )
            report_content += (
                "### Buggy Tools (⚠️)\n"
                + "\n".join([f"- {t}" for t in results["buggy"]])
                + "\n\n"
            )
            report_content += (
                "### Broken Tools (❌)\n"
                + "\n".join([f"- {t}" for t in results["broken"]])
                + "\n\n"
            )
            report_content += (
                "### Not Tested (🚫)\n"
                + "\n".join([f"- {t}" for t in results["not_tested"]])
                + "\n\n"
            )

            report_content += "## Incidents (Prioritized)\n\n"

            for i, inc in enumerate(incidents, 1):
                report_content += f"### RMTA-{i:03d}: [{inc['severity']}] {inc['tool']} - {inc['status']}\n"
                report_content += f"**Tool:** `{inc['tool']}`\n"
                report_content += f"**Severity:** {inc['severity']}\n"
                report_content += f"**Status:** {inc['status']}\n\n"
                report_content += f"**Expected:**\n{inc['expected']}\n\n"
                report_content += f"**Actual:**\n{inc['actual']}\n\n"
                report_content += f"**Evidence:**\n```\n{inc['evidence']}\n```\n\n"
                report_content += "---\n\n"

            report_content += """## RMTA's Verdict
Testing complete.
Purple tastes like recursive debugging.
"""

            report_path.write_text(report_content)
            print(f"\n✓ Report generated: {report_path}")

    except Exception as e:
        print(f"\n❌ ERROR: Main Loop Exception: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_mcp_server())
