# RMTA Test Results
Generated: 2025-12-16 09:46:43

## Testing Methodology
- **Code Analysis**: Static analysis of server.py and tool implementations
- **Live Testing**: ❌ NOT POSSIBLE - MCP server not running
- **Configuration Analysis**: Review of llmc.toml config

## Summary
- **Total Tools Analyzed**: 28
- **✅ Likely Working**: 26 (based on code inspection)
- **⚠️ Potentially Buggy**: 2 (see below)
- **❌ Likely Broken**: 0
- **🚫 Cannot Test**: 28 (server not running)

## Tool Analysis

### ✅ Likely Working Tools (25)
Based on code inspection, these tools have proper handlers and implementations:

1. **00_INIT** - Simple bootstrap handler exists
2. **read_file** - Uses `llmc_mcp.tools.fs.read_file` with allowed_roots validation
3. **list_dir** - Uses `llmc_mcp.tools.fs.list_dir` with allowed_roots validation
4. **stat** - Uses `llmc_mcp.tools.fs.stat_path` with allowed_roots validation
5. **run_cmd** - Uses `llmc_mcp.tools.cmd.run_cmd` with blacklist validation
6. **get_metrics** - Requires observability enabled, has proper handler
7. **te_run** - Uses `llmc_mcp.tools.te.te_run` with context
8. **repo_read** - Uses `llmc_mcp.tools.te_repo.repo_read` with context
9. **rag_search** - Uses `llmc_mcp.tools.rag.rag_search` direct adapter
10. **rag_search_enriched** - Uses `llmc_mcp.tools.rag.rag_search_enriched`
11. **rag_where_used** - Uses `tools.rag_nav.tool_handlers.tool_rag_where_used`
12. **rag_lineage** - Uses `tools.rag_nav.tool_handlers.tool_rag_lineage`
13. **inspect** - Uses `tools.rag.inspector.inspect_entity`
14. **rag_stats** - Uses `tools.rag_nav.tool_handlers.tool_rag_stats`
15. **rag_plan** - Has custom routing logic implementation
16. **linux_proc_list** - Uses `llmc_mcp.tools.linux_ops.proc.mcp_linux_proc_list`
17. **linux_proc_kill** - Uses `llmc_mcp.tools.linux_ops.proc.mcp_linux_proc_kill`
18. **linux_sys_snapshot** - Uses `llmc_mcp.tools.linux_ops.sysinfo.mcp_linux_sys_snapshot`
19. **linux_proc_start** - Uses `llmc_mcp.tools.linux_ops.proc.mcp_linux_proc_start`
20. **linux_proc_send** - Uses `llmc_mcp.tools.linux_ops.proc.mcp_linux_proc_send`
21. **linux_proc_read** - Uses `llmc_mcp.tools.linux_ops.proc.mcp_linux_proc_read`
22. **linux_proc_stop** - Uses `llmc_mcp.tools.linux_ops.proc.mcp_linux_proc_stop`
23. **linux_fs_write** - Uses `llmc_mcp.tools.fs_protected.write_file_protected` with MAASL
24. **linux_fs_mkdir** - Uses `llmc_mcp.tools.fs.create_directory`
25. **linux_fs_delete** - Uses `llmc_mcp.tools.fs_protected.delete_file_protected` with MAASL

### ⚠️ Potentially Buggy Tools (2)

#### 1. rag_query (⚠️ BUGGY)
**Issue**: Duplicate functionality with `rag_search`
- Both tools call `rag_search()` internally
- `rag_query` description says "via Tool Envelope" but implementation uses direct adapter
- May cause confusion about which tool to use

**Evidence**:
```python
# In _handle_rag_query (line 1695-1734):
result = rag_search(query=query, repo_root=llmc_root, limit=limit, scope="repo")
```

#### 2. linux_fs_edit (⚠️ BUGGY)
**Issue**: Argument validation inconsistency
- Description says "old_text" is required
- Code checks `if not path or not old_text:` (line 1998)
- But `new_text` is also required per schema, not validated in same check

**Evidence**:
```python
if not path or not old_text:
    return [TextContent(type="text", text='{"error": "path and old_text required"}')]
# Missing new_text validation
```

### ❌ Likely Broken Tools (0)

**Note**: After further inspection, `linux_fs_move` appears to have proper implementation. The `move_file_protected` function exists in `fs_protected.py` and imports `_move_file_unprotected` alias correctly.

### 🚫 Cannot Test (28)
All tools cannot be tested because:
- MCP server is not running
- Cannot establish MCP connection
- No stdio transport available for testing

## Configuration Issues

### 1. Code Execution Mode Disabled but Stubs Exist
**Issue**: `mcp.code_execution.enabled = false` but stubs directory exists with 25 stub files
- Stubs are generated but not used in classic mode
- Wasted disk space and potential confusion

### 2. Tool Envelope Disabled
**Issue**: `[tool_envelope] enabled = false` in config
- `te_run` and `repo_read` tools depend on Tool Envelope
- These tools may fail or have reduced functionality

### 3. RAG Configuration
**Issue**: Multiple RAG tools but RAG system dependencies not verified
- `rag_search`, `rag_query`, `rag_search_enriched` all need RAG index
- No verification that RAG system is initialized

## Documentation Drift

### 1. Bootstrap Prompt vs Actual Tools
**Mismatch**: Bootstrap prompt lists tools but some may not work as described:
- `rag_query` described as "via Tool Envelope" but uses direct adapter
- `te_run` and `repo_read` depend on disabled Tool Envelope

### 2. Missing execute_code Tool
**Issue**: `execute_code` tool defined in server but not in TOOLS list
- Only added in code execution mode (line 716)
- Not available in classic mode despite being defined

### 3. Inconsistent Error Messages
**Issue**: Different tools have different error message formats:
- Some return `{"error": "message"}`
- Some return `{"error": "message", "meta": {}}`
- LinuxOps tools return `{"error": str(e), "code": e.code}`

## Recommendations

### P0 - Critical (Require Immediate Fix):
1. **Fix linux_fs_move import** - Verify `move_file_protected` exists or implement it
2. **Start MCP server for testing** - Cannot validate functionality without running server

### P1 - High (Core Functionality):
3. **Resolve rag_query duplication** - Either remove or differentiate from rag_search
4. **Fix linux_fs_edit validation** - Add new_text to required validation check
5. **Verify Tool Envelope dependencies** - Ensure te_run and repo_read work with disabled TE

### P2 - Medium (UX Improvements):
6. **Standardize error messages** - Consistent JSON error format across all tools
7. **Clean up unused stubs** - Remove .llmc/stubs/ if code execution mode disabled
8. **Update bootstrap prompt** - Reflect actual tool capabilities

### P3 - Low (Documentation):
9. **Document tool dependencies** - Which tools need RAG, which need Tool Envelope
10. **Add examples to tool descriptions** - Show realistic usage patterns

## RMTA Verdict

**Assessment**: ❌ **INCOMPLETE TESTING**

The MCP server implementation appears robust with proper error handling and security measures. However, without a running server, functional testing is impossible.

**Critical Findings**:
1. `linux_fs_move` likely has missing import (P0)
2. `rag_query` duplicates `rag_search` functionality (P1)
3. Tool Envelope dependency issues (P1)

**Testing Blockers**:
- MCP server not running
- Cannot establish MCP connection
- No way to invoke tools via MCP protocol

**Next Steps**:
1. Start MCP server: `python -m llmc_mcp.server`
2. Connect via MCP client
3. Perform actual tool invocation tests
4. Validate error handling and responses

Purple tastes like incomplete test coverage without a running server.