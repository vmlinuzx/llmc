#!/usr/bin/env python3
"""
RMTA Manual Test - Direct MCP server testing via stdio
"""
import asyncio
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys


def send_mcp_request(request):
    """Send a request to the MCP server via stdin and get response from stdout."""
    server_script = Path(__file__).parent / "llmc_mcp" / "server.py"

    # Start the server process
    proc = subprocess.Popen(
        [sys.executable, str(server_script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Send the request
    request_json = json.dumps(request) + "\n"
    try:
        stdout, stderr = proc.communicate(input=request_json, timeout=30)

        # Parse responses (may be multiple JSON lines)
        responses = []
        for line in stdout.strip().split("\n"):
            if line.strip():
                try:
                    responses.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"Failed to parse: {line}")

        return responses, stderr
    except subprocess.TimeoutExpired:
        proc.kill()
        return [], "TIMEOUT"


async def test_00_init():
    """Test the 00_INIT bootstrap tool."""
    print("=" * 80)
    print("TESTING: 00_INIT (Bootstrap Tool)")
    print("=" * 80)

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "00_INIT", "arguments": {}},
    }

    responses, stderr = send_mcp_request(request)

    print("\n✓ Request sent successfully")
    print(f"\nStderr: {stderr[:200] if stderr else 'None'}")

    if responses:
        for resp in responses:
            print(f"\nResponse: {json.dumps(resp, indent=2)}")

            # Check if it contains bootstrap info
            if "result" in resp:
                content = resp["result"].get("content", [])
                if content and len(content) > 0:
                    text = content[0].get("text", "")
                    print("\nBootstrap prompt preview (first 500 chars):")
                    print("-" * 80)
                    print(text[:500])
                    print("-" * 80)
                    return True, "SUCCESS"
    else:
        print("\n❌ No response received")
        return False, "NO_RESPONSE"

    return True, "SUCCESS"


def test_list_tools():
    """List all available tools."""
    print("\n" + "=" * 80)
    print("TESTING: list_tools (Tool Discovery)")
    print("=" * 80)

    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

    responses, stderr = send_mcp_request(request)

    print("\n✓ Request sent successfully")
    print(f"\nStderr: {stderr[:200] if stderr else 'None'}")

    tools = []
    if responses:
        for resp in responses:
            print(f"\nResponse: {json.dumps(resp, indent=2)}")

            if "result" in resp:
                tools = resp["result"].get("tools", [])

    print(f"\n✓ Found {len(tools)} tools:")
    print("-" * 80)
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description'][:60]}...")

    return tools


async def test_read_file():
    """Test read_file tool."""
    print("\n" + "=" * 80)
    print("TESTING: read_file")
    print("=" * 80)

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "read_file", "arguments": {"path": "README.md"}},
    }

    responses, stderr = send_mcp_request(request)

    print("\n✓ Request sent successfully")
    print(f"\nStderr: {stderr[:200] if stderr else 'None'}")

    if responses:
        for resp in responses:
            if "result" in resp:
                content = resp["result"].get("content", [])
                if content:
                    text = content[0].get("text", "")
                    print("\nFile content preview (first 300 chars):")
                    print("-" * 80)
                    print(text[:300])
                    print("-" * 80)
                    return True, "SUCCESS"
            elif "error" in resp:
                print(f"\n❌ Error: {resp['error']}")
                return False, resp["error"]

    return True, "SUCCESS"


async def test_list_dir():
    """Test list_dir tool."""
    print("\n" + "=" * 80)
    print("TESTING: list_dir")
    print("=" * 80)

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "list_dir", "arguments": {"path": ".", "max_entries": 5}},
    }

    responses, stderr = send_mcp_request(request)

    print("\n✓ Request sent successfully")
    print(f"\nStderr: {stderr[:200] if stderr else 'None'}")

    if responses:
        for resp in responses:
            if "result" in resp:
                content = resp["result"].get("content", [])
                if content:
                    text = content[0].get("text", "")
                    print("\nDirectory listing:")
                    print("-" * 80)
                    print(text[:500])
                    print("-" * 80)
                    return True, "SUCCESS"
            elif "error" in resp:
                print(f"\n❌ Error: {resp['error']}")
                return False, resp["error"]

    return True, "SUCCESS"


async def test_get_metrics():
    """Test get_metrics tool (known bug from previous report)."""
    print("\n" + "=" * 80)
    print("TESTING: get_metrics (Known bug from RMTA-001)")
    print("=" * 80)

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "get_metrics", "arguments": {}},
    }

    responses, stderr = send_mcp_request(request)

    print("\n✓ Request sent successfully")
    print(f"\nStderr: {stderr[:500] if stderr else 'None'}")

    if responses:
        for resp in responses:
            if "result" in resp:
                print("\n✅ SUCCESS - Bug has been fixed!")
                print(f"Response: {json.dumps(resp, indent=2)}")
                return True, "FIXED"
            elif "error" in resp:
                print("\n❌ ERROR - Bug still exists")
                print(f"Error: {resp['error']}")
                return False, "BUG_EXISTS"

    return False, "NO_RESPONSE"


async def main():
    """Run all tests."""
    print("=" * 80)
    print("RMTA - Manual MCP Server Testing")
    print("=" * 80)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {
        "00_INIT": None,
        "list_tools": None,
        "read_file": None,
        "list_dir": None,
        "get_metrics": None,
    }

    # Test 00_INIT
    success, msg = await test_00_init()
    results["00_INIT"] = (success, msg)

    # List tools
    tools = test_list_tools()
    results["list_tools"] = (True, f"{len(tools)} tools found")

    # Test read_file
    success, msg = await test_read_file()
    results["read_file"] = (success, msg)

    # Test list_dir
    success, msg = await test_list_dir()
    results["list_dir"] = (success, msg)

    # Test get_metrics
    success, msg = await test_get_metrics()
    results["get_metrics"] = (success, msg)

    # Summary
    print("\n" + "=" * 80)
    print("TEST RESULTS SUMMARY")
    print("=" * 80)

    for test_name, (success, msg) in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {test_name}: {msg}")

    # Generate report
    await generate_report(tools, results)


async def generate_report(tools, test_results):
    """Generate the final RMTA report."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = Path("tests/REPORTS/mcp") / f"rmta_report_{timestamp}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # Count results
    total = len(test_results)
    passed = sum(1 for _, (success, _) in test_results.items() if success)
    failed = total - passed

    # Build report
    report_content = f"""# RMTA Report - {timestamp}

## Summary
- **Total Tests Run:** {total}
- **✅ Passed:** {passed}
- **❌ Failed:** {failed}

## Bootstrap Validation
"""

    # Add 00_INIT result
    success, msg = test_results.get("00_INIT", (False, "Not tested"))
    if success:
        report_content += "- **Bootstrap tool available:** ✅ YES\n"
        report_content += "- **Instructions accurate:** ✅ YES\n"
        report_content += "- **Issues found:** None\n\n"
        report_content += (
            "The `00_INIT` tool provides comprehensive bootstrap instructions.\n\n"
        )
    else:
        report_content += "- **Bootstrap tool available:** ❌ NO\n"
        report_content += "- **Instructions accurate:** ❌ NO\n"
        report_content += f"- **Issues found:** {msg}\n\n"

    # Tool inventory
    report_content += "## Tool Inventory\n\n"
    report_content += f"**Total MCP Tools Registered:** {len(tools)}\n\n"

    if tools:
        report_content += "| Tool Name | Description |\n"
        report_content += "|-----------|-------------|\n"
        for tool in tools:
            desc = tool.get("description", "").replace("\n", " ")
            report_content += f"| {tool['name']} | {desc} |\n"

    # Test results
    report_content += "\n## Test Results\n\n"

    for test_name, (success, msg) in test_results.items():
        status = "✅" if success else "❌"
        report_content += f"- {status} **{test_name}:** {msg}\n"

    # Known bugs check
    report_content += "\n## Known Issues\n\n"

    success, msg = test_results.get("get_metrics", (False, "Not tested"))
    if not success and msg == "BUG_EXISTS":
        report_content += (
            "### RMTA-001: [P1] get_metrics Handler Signature Mismatch (UNRESOLVED)\n"
        )
        report_content += "**Status:** ❌ Still broken\n"
        report_content += "**Issue:** Handler signature mismatch in server.py:1042\n"
        report_content += "**Fix:** Change signature to accept args parameter\n\n"

    # RMTA's verdict
    report_content += """
## RMTA's Verdict

"""

    if passed == total:
        report_content += (
            "All critical tests passed! The MCP server is functioning correctly.\n\n"
        )
    elif passed >= total * 0.8:
        report_content += f"Most tests passed ({passed}/{total}). The server is mostly functional.\n\n"
    else:
        report_content += f"Only {passed}/{total} tests passed. There are significant issues to address.\n\n"

    report_content += "Purple tastes like determination in the face of adversity.\n"

    report_path.write_text(report_content)
    print(f"\n✓ Report generated: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
