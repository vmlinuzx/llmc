import asyncio
import json
import sys
import os
import shutil
from datetime import datetime
from pathlib import Path

# Add repo root to path
REPO_ROOT = os.getcwd()
sys.path.append(REPO_ROOT)

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("CRITICAL: mcp module not found. Please install dependencies.")
    sys.exit(1)

REPORT_DIR = Path("tests/REPORTS/mcp")
REPORT_DIR.mkdir(parents=True, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_FILE = REPORT_DIR / f"rmta_report_{TIMESTAMP}.md"

results = {
    "total": 0,
    "passed": 0,
    "buggy": 0,
    "broken": 0,
    "not_tested": 0,
    "details": []
}

def log_result(tool_name, status, notes, evidence):
    results["total"] += 1
    if status == "✅":
        results["passed"] += 1
    elif status == "⚠️":
        results["buggy"] += 1
    elif status == "❌":
        results["broken"] += 1
    else:
        results["not_tested"] += 1

    results["details"].append({
        "tool": tool_name,
        "status": status,
        "notes": notes,
        "evidence": evidence
    })
    print(f"[{status}] {tool_name}: {notes}")

def parse_mcp_response(res):
    """Helper to parse MCP text content as JSON if possible."""
    if not res.content:
        return None, "Empty content"

    text = res.content[0].text
    try:
        data = json.loads(text)
        return data, text
    except json.JSONDecodeError:
        return None, text

async def run_tests():
    print(f"Starting RMTA Test Run at {TIMESTAMP}")

    # Phase 1: Bootstrap

    env = {**os.environ, "PYTHONPATH": REPO_ROOT, "LLMC_ISOLATED": "1"}

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "llmc_mcp.server", "--config", "tests/mcp/test_config.toml"],
        env=env
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                print("Connected to MCP server.")
                await session.initialize()

                # Phase 2: Discovery
                tools_response = await session.list_tools()
                available_tools = {t.name: t for t in tools_response.tools}
                print(f"Discovered {len(available_tools)} tools.")

                # Verify Bootstrap
                if "00_INIT" in available_tools:
                    try:
                        res = await session.call_tool("00_INIT")
                        log_result("00_INIT", "✅", "Bootstrap tool works", res.content[0].text)
                    except Exception as e:
                        log_result("00_INIT", "❌", f"Bootstrap failed: {e}", str(e))
                else:
                    log_result("00_INIT", "⚠️", "Bootstrap tool missing in Classic Mode", "Tool not found in list")

                # Phase 3: Systematic Testing

                # 1. read_file
                if "read_file" in available_tools:
                    try:
                        res = await session.call_tool("read_file", arguments={"path": "llmc.toml"})
                        data, text = parse_mcp_response(res)
                        if data and "error" in data:
                             log_result("read_file", "❌", "Error reading file", text)
                        elif data and "data" in data:
                             log_result("read_file", "✅", "Read llmc.toml", f"Content length: {len(data['data'])}")
                        else:
                             log_result("read_file", "⚠️", "Unexpected response format", text)
                    except Exception as e:
                        log_result("read_file", "❌", f"Exception: {e}", str(e))

                # 2. list_dir
                if "list_dir" in available_tools:
                    try:
                        res = await session.call_tool("list_dir", arguments={"path": "."})
                        data, text = parse_mcp_response(res)
                        if data and "error" in data:
                             log_result("list_dir", "❌", "Error listing dir", text)
                        elif data and "data" in data:
                             log_result("list_dir", "✅", "Listed root dir", f"Entries: {len(data['data'])}")
                        else:
                             log_result("list_dir", "⚠️", "Unexpected response format", text)
                    except Exception as e:
                        log_result("list_dir", "❌", f"Exception: {e}", str(e))

                # 3. stat
                if "stat" in available_tools:
                    try:
                        res = await session.call_tool("stat", arguments={"path": "llmc.toml"})
                        data, text = parse_mcp_response(res)
                        if data and "error" in data:
                             log_result("stat", "❌", "Error stating file", text)
                        elif data and "data" in data:
                             log_result("stat", "✅", "Stated llmc.toml", text)
                        else:
                             log_result("stat", "⚠️", "Unexpected response format", text)
                    except Exception as e:
                         log_result("stat", "❌", f"Exception: {e}", str(e))

                # 4. run_cmd
                if "run_cmd" in available_tools:
                    try:
                        res = await session.call_tool("run_cmd", arguments={"command": "echo 'Hello MCP'"})
                        data, text = parse_mcp_response(res)
                        if data and "error" in data:
                             log_result("run_cmd", "❌", "Command failed", text)
                        elif data and "stdout" in data:
                            if "Hello MCP" in data["stdout"]:
                                log_result("run_cmd", "✅", "Echo works", data["stdout"])
                            else:
                                log_result("run_cmd", "⚠️", "Unexpected output", data["stdout"])
                        else:
                            log_result("run_cmd", "⚠️", "Unexpected response format", text)
                    except Exception as e:
                        log_result("run_cmd", "❌", f"Exception: {e}", str(e))

                # 5. rag_search
                if "rag_search" in available_tools:
                    try:
                        res = await session.call_tool("rag_search", arguments={"query": "server"})
                        data, text = parse_mcp_response(res)
                        if data and "error" in data:
                            log_result("rag_search", "❌", "RAG Error (Missing Index?)", text)
                        elif data and "results" in data:
                            log_result("rag_search", "✅", "Search successful", f"Results: {len(data['results'])}")
                        else:
                            log_result("rag_search", "✅", "Search executed (check structure)", text[:200])
                    except Exception as e:
                        log_result("rag_search", "❌", f"Exception: {e}", str(e))

                # 6. get_metrics
                if "get_metrics" in available_tools:
                    try:
                        res = await session.call_tool("get_metrics")
                        data, text = parse_mcp_response(res)
                        if data and "error" in data:
                            log_result("get_metrics", "❌", "Error getting metrics", text)
                        else:
                            log_result("get_metrics", "✅", "Got metrics", text[:100])
                    except Exception as e:
                        log_result("get_metrics", "❌", f"Exception: {e}", str(e))

                # 7. te_run
                if "te_run" in available_tools:
                    try:
                        res = await session.call_tool("te_run", arguments={"args": ["ls", "-la"]})
                        data, text = parse_mcp_response(res)
                        if data and "error" in data:
                             log_result("te_run", "❌", "te_run failed", text)
                        else:
                             log_result("te_run", "✅", "te_run ls works", text[:100])
                    except Exception as e:
                        log_result("te_run", "❌", f"Exception: {e}", str(e))

                # 8. linux_fs_write
                if "linux_fs_write" in available_tools:
                     test_file = "tests/mcp/rmta_write_test.txt"
                     try:
                         res = await session.call_tool("linux_fs_write", arguments={"path": test_file, "content": "RMTA was here"})
                         data, text = parse_mcp_response(res)
                         if data and "error" in data:
                             log_result("linux_fs_write", "❌", "Write failed", text)
                         elif data and "data" in data:
                             log_result("linux_fs_write", "✅", "Write successful", text)
                             # Clean up
                             try:
                                 os.remove(test_file)
                             except OSError:
                                 pass
                         else:
                             log_result("linux_fs_write", "⚠️", "Unexpected response format", text)
                     except Exception as e:
                         log_result("linux_fs_write", "❌", f"Exception: {e}", str(e))

                # 9. repo_read
                if "repo_read" in available_tools:
                    try:
                        res = await session.call_tool("repo_read", arguments={"root": REPO_ROOT, "path": "llmc.toml"})
                        data, text = parse_mcp_response(res)
                        if data and "error" in data:
                             log_result("repo_read", "❌", "Error reading repo file", text)
                        else:
                             log_result("repo_read", "✅", "Read repo file", text[:100])
                    except Exception as e:
                        log_result("repo_read", "❌", f"Exception: {e}", str(e))

                # 10. linux_fs_mkdir & delete
                if "linux_fs_mkdir" in available_tools:
                    test_dir = "tests/mcp/rmta_test_dir"
                    try:
                        res = await session.call_tool("linux_fs_mkdir", arguments={"path": test_dir})
                        data, text = parse_mcp_response(res)
                        if data and "error" in data:
                             log_result("linux_fs_mkdir", "❌", "Mkdir failed", text)
                        else:
                             log_result("linux_fs_mkdir", "✅", "Mkdir successful", text)

                             # Cleanup with delete
                             if "linux_fs_delete" in available_tools:
                                 res_del = await session.call_tool("linux_fs_delete", arguments={"path": test_dir, "recursive": True})
                                 data_del, text_del = parse_mcp_response(res_del)
                                 if data_del and "error" in data_del:
                                     log_result("linux_fs_delete", "❌", "Delete failed", text_del)
                                 else:
                                     log_result("linux_fs_delete", "✅", "Delete successful", text_del)
                    except Exception as e:
                        log_result("linux_fs_mkdir", "❌", f"Exception: {e}", str(e))

                # 11. linux_sys_snapshot
                if "linux_sys_snapshot" in available_tools:
                    try:
                        res = await session.call_tool("linux_sys_snapshot")
                        data, text = parse_mcp_response(res)
                        if data and "error" in data:
                             log_result("linux_sys_snapshot", "❌", "Snapshot failed", text)
                        else:
                             log_result("linux_sys_snapshot", "✅", "Snapshot successful", text[:100])
                    except Exception as e:
                        log_result("linux_sys_snapshot", "❌", f"Exception: {e}", str(e))

                # 12. linux_proc_list
                if "linux_proc_list" in available_tools:
                    try:
                        res = await session.call_tool("linux_proc_list")
                        data, text = parse_mcp_response(res)
                        if data and "error" in data:
                             log_result("linux_proc_list", "❌", "Proc list failed", text)
                        else:
                             log_result("linux_proc_list", "✅", "Proc list successful", text[:100])
                    except Exception as e:
                        log_result("linux_proc_list", "❌", f"Exception: {e}", str(e))

                # 13. RAG Group (likely to fail)
                rag_tools = ["rag_query", "rag_search_enriched", "rag_stats", "rag_plan"]
                for rt in rag_tools:
                    if rt in available_tools:
                        try:
                            # Use inputSchema to check required args
                            schema = available_tools[rt].inputSchema
                            args = {}
                            if "required" in schema:
                                for req in schema["required"]:
                                    if req == "query":
                                        args["query"] = "test"
                                    elif req == "symbol":
                                        args["symbol"] = "McpServer"
                                    elif req == "path":
                                        args["path"] = "llmc.toml"

                            res = await session.call_tool(rt, arguments=args)
                            data, text = parse_mcp_response(res)
                            if data and "error" in data:
                                 log_result(rt, "❌", "RAG Tool Error", text)
                            else:
                                 log_result(rt, "✅", "RAG Tool called", text[:100])
                        except Exception as e:
                            log_result(rt, "❌", f"Exception: {e}", str(e))

                # 14. linux_fs_edit
                if "linux_fs_edit" in available_tools:
                    # Create a file first
                    fpath = "tests/mcp/edit_test.txt"
                    with open(fpath, "w") as f:
                        f.write("Hello Old World")

                    try:
                        res = await session.call_tool("linux_fs_edit", arguments={"path": fpath, "old_text": "Old", "new_text": "New"})
                        data, text = parse_mcp_response(res)
                        if data and "error" in data:
                             log_result("linux_fs_edit", "❌", "Edit failed", text)
                        else:
                             log_result("linux_fs_edit", "✅", "Edit successful", text)
                    except Exception as e:
                        log_result("linux_fs_edit", "❌", f"Exception: {e}", str(e))
                    finally:
                        if os.path.exists(fpath):
                            os.remove(fpath)

                # 15. More RAG Tools
                rag_nav_tools = ["rag_where_used", "rag_lineage", "inspect"]
                for rt in rag_nav_tools:
                    if rt in available_tools:
                        try:
                            args = {}
                            if rt == "inspect":
                                args = {"path": "llmc.toml"}
                            else:
                                args = {"symbol": "McpServer"}

                            res = await session.call_tool(rt, arguments=args)
                            data, text = parse_mcp_response(res)
                            if data and "error" in data:
                                 log_result(rt, "❌", "RAG Tool Error", text)
                            else:
                                 log_result(rt, "✅", "RAG Tool called", text[:100])
                        except Exception as e:
                            log_result(rt, "❌", f"Exception: {e}", str(e))

                # 16. linux_fs_move
                if "linux_fs_move" in available_tools:
                    src = "tests/mcp/move_test_src.txt"
                    dst = "tests/mcp/move_test_dst.txt"
                    with open(src, "w") as f:
                        f.write("Move me")
                    try:
                        res = await session.call_tool("linux_fs_move", arguments={"source": src, "dest": dst})
                        data, text = parse_mcp_response(res)
                        if data and "error" in data:
                             log_result("linux_fs_move", "❌", "Move failed", text)
                        else:
                             log_result("linux_fs_move", "✅", "Move successful", text)
                    except Exception as e:
                        log_result("linux_fs_move", "❌", f"Exception: {e}", str(e))
                    finally:
                        if os.path.exists(src): os.remove(src)
                        if os.path.exists(dst): os.remove(dst)

                # Loop through remaining tools
                covered_tools = [
                    "00_INIT", "read_file", "list_dir", "stat", "run_cmd", "rag_search", "get_metrics", "te_run", "linux_fs_write",
                    "repo_read", "linux_fs_mkdir", "linux_fs_delete", "linux_sys_snapshot", "linux_proc_list",
                    "rag_query", "rag_search_enriched", "rag_stats", "rag_plan", "linux_fs_edit",
                    "rag_where_used", "rag_lineage", "inspect", "linux_fs_move"
                ]
                for name in available_tools:
                    if name not in covered_tools:
                         log_result(name, "🚫", "Not specifically tested yet", "Skipped in this pass")

    except Exception as e:
        print(f"CRITICAL ERROR running tests: {e}")

    # Generate Report
    generate_report()

def generate_report():
    report_content = f"""# RMTA Report - {TIMESTAMP}

## Summary
- **Total Tools Tested:** {results['total']}
- **✅ Working:** {results['passed']}
- **⚠️ Buggy:** {results['buggy']}
- **❌ Broken:** {results['broken']}
- **🚫 Not Tested:** {results['not_tested']}

## Bootstrap Validation
- Bootstrap tool available: {"YES" if any(r['tool'] == '00_INIT' and r['status'] == '✅' for r in results['details']) else "NO"}
- Issues found:
  - { "00_INIT missing in Classic Mode" if any(r['tool'] == '00_INIT' and r['status'] != '✅' for r in results['details']) else "None" }

## Test Results

### Working Tools (✅)
"""
    for r in results['details']:
        if r['status'] == '✅':
            report_content += f"- **{r['tool']}**: {r['notes']}\n"

    report_content += "\n### Buggy Tools (⚠️)\n"
    for r in results['details']:
        if r['status'] == '⚠️':
            report_content += f"- **{r['tool']}**: {r['notes']}\n  Evidence: {r['evidence']}\n"

    report_content += "\n### Broken Tools (❌)\n"
    for r in results['details']:
        if r['status'] == '❌':
            report_content += f"- **{r['tool']}**: {r['notes']}\n  Evidence: {r['evidence']}\n"

    report_content += "\n### Untested Tools (🚫)\n"
    for r in results['details']:
        if r['status'] == '🚫':
            report_content += f"- **{r['tool']}**\n"

    report_content += """
## Incidents (Prioritized)
"""
    count = 1
    for r in results['details']:
        if r['status'] == '❌' or r['status'] == '⚠️':
            severity = "P0" if r['status'] == '❌' else "P2"
            report_content += f"\n### RMTA-{count:03d}: [{severity}] {r['tool']} Failure\n"
            report_content += f"**Tool:** `{r['tool']}`\n"
            report_content += f"**Severity:** {severity}\n"
            report_content += f"**What I Tried:** Automated test call.\n"
            report_content += f"**Actual:** {r['notes']}\n"
            report_content += f"**Evidence:**\n```\n{r['evidence']}\n```\n"
            count += 1

    report_content += """
## Recommendations
1. Fix critical P0 issues (broken tools).
2. Address P2 bugs (missing handlers/metadata).
3. Investigate untested tools manually.

## RMTA's Verdict
Automated test run completed.
"""

    with open(REPORT_FILE, "w") as f:
        f.write(report_content)

    print(f"Report written to {REPORT_FILE}")

if __name__ == "__main__":
    asyncio.run(run_tests())
