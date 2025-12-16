# RMTA UX Analysis
Generated: 2025-12-16 09:46:43

## Overview
Analysis of user experience, documentation accuracy, and potential confusion points in the LLMC MCP server.

## UX Issues Found

### 1. Tool Naming Inconsistency
**Issue**: Mixed naming conventions cause confusion
- `rag_search` vs `rag_query` - Similar functionality, different names
- `linux_fs_*` vs just `fs_*` - Inconsistent prefix usage
- `te_run` vs `run_cmd` - One uses Tool Envelope, one doesn't

**Impact**: Users must remember which tool to use for similar operations

### 2. Error Message Inconsistency
**Issue**: Different error formats across tools
- Basic tools: `{"error": "message"}`
- FS tools: `{"error": "message", "meta": {}}`
- LinuxOps: `{"error": str(e), "code": e.code}`
- RAG tools: Varies by implementation

**Example**:
```json
// rag_search error
{"error": "query is required"}

// linux_proc_list error
{"error": "Permission denied", "code": "PERMISSION_DENIED"}

// read_file error
{"error": "path is required", "meta": {}}
```

**Impact**: Users must handle multiple error formats in client code

### 3. Required Field Validation Gaps
**Issue**: Some tools don't validate all required fields consistently
- `linux_fs_edit`: Checks `path` and `old_text` but not `new_text` in initial validation
- `te_run`: Validates `args` is list but not that it's non-empty

**Impact**: Tools may fail later with less helpful error messages

### 4. Default Value Documentation
**Issue**: Default values not always clear in tool descriptions
- `rag_search`: `limit` default=5, but range is 1-20 (documented in code, not description)
- `linux_proc_list`: `max_results` default=200, range 1-5000
- `rag_search_enriched`: `graph_depth` default=1, range 0-3

**Impact**: Users may use invalid values without knowing constraints

### 5. Tool Overlap and Duplication
**Issue**: Multiple tools with similar functionality
- `rag_search` vs `rag_query` - Both do RAG search, one "via Tool Envelope"
- `read_file` vs `repo_read` - Both read files, different parameter structures
- `run_cmd` vs `te_run` - Both execute commands, different wrappers

**Impact**: Decision paralysis - which tool should I use?

### 6. Missing Examples in Tool Descriptions
**Issue**: Tool descriptions lack usage examples
- Complex tools like `rag_search_enriched` need example parameters
- `inspect` tool has many options but no examples
- `linux_proc_start/send/read/stop` workflow not documented

**Impact**: Users must guess correct parameter formats

## Documentation Drift

### 1. Bootstrap Prompt vs Reality
**Mismatches found**:
- Prompt says `te_run` and `repo_read` are available, but Tool Envelope is disabled in config
- Prompt lists `rag_query` as "via Tool Envelope" but implementation uses direct adapter
- Prompt doesn't mention `execute_code` tool (only in code execution mode)

### 2. Config vs Implementation
**Mismatches found**:
- `mcp.code_execution.enabled = false` but stubs directory exists with 25 files
- `[tool_envelope] enabled = false` but tools depending on it are still registered
- `mcp.tools.enable_run_cmd = true` but blacklist is empty (commented out)

### 3. Tool Descriptions vs Implementation
**Mismatches found**:
- `rag_query` description: "via Tool Envelope" but uses direct `rag_search()`
- `linux_fs_edit` description: mentions `old_text` required, code validates it but not `new_text`
- `execute_code` tool: Extensive documentation in code but not in bootstrap prompt

## Agent Experience Notes

### Positive Aspects:
1. **Good error messages** for path validation with `allowed_roots` hints
2. **Security measures** in place (MAASL protection, allowed_roots validation)
3. **Observability integration** with `get_metrics` tool
4. **Smart grep interception** in `run_cmd` - nice UX touch

### Confusing Aspects:
1. **Too many similar tools** - 28 tools is overwhelming
2. **Mode complexity** - Classic vs Code Execution vs Hybrid modes
3. **Dependencies unclear** - Which tools need RAG? Which need Tool Envelope?
4. **Stubs directory unused** - Generated but not used in classic mode

### Surprising Behavior:
1. **Smart grep** in `run_cmd` intercepts grep commands and shows RAG results
2. **MAASL protection** on write operations - good for multi-agent safety
3. **LinuxOps tools** available - full process management capability

## Recommendations by Priority

### P0 - Critical UX Issues:
1. **Standardize error messages** - Single JSON format across all tools
2. **Fix bootstrap prompt accuracy** - Update to match actual tool capabilities
3. **Resolve tool duplication** - Merge `rag_search` and `rag_query` or clearly differentiate

### P1 - High Impact UX:
4. **Add examples to tool descriptions** - Show realistic usage for complex tools
5. **Improve required field validation** - Consistent validation across all tools
6. **Document default values and ranges** - In tool descriptions, not just code

### P2 - Medium Impact UX:
7. **Create tool categories** - Group related tools in bootstrap prompt
8. **Add tool dependency documentation** - Which tools need RAG/TE enabled
9. **Clean up unused stubs** - Remove if code execution mode disabled

### P3 - Low Impact UX:
10. **Consistent naming** - Consider `fs_` prefix instead of `linux_fs_`
11. **Add tool aliases** - For common operations with multiple tools
12. **Progress indicators** - For long-running operations like RAG search

## Testing Limitations

### Blockers for Proper UX Testing:
1. **MCP server not running** - Cannot test actual tool invocation
2. **No MCP client available** - Cannot test end-to-end workflow
3. **RAG system dependency** - Cannot test RAG tools without index
4. **Tool Envelope disabled** - Cannot test `te_run` and `repo_read` functionality

### Partial Testing Possible:
- Code analysis for error handling
- Configuration validation
- Documentation accuracy checking
- Import and dependency verification

## Conclusion

The LLMC MCP server has a **comprehensive but complex** toolset. The implementation appears robust with good security measures, but the UX suffers from:

1. **Tool overload** - 28 tools is overwhelming
2. **Inconsistency** - Error formats, naming, validation
3. **Documentation drift** - Bootstrap prompt doesn't match reality
4. **Unclear dependencies** - Which tools need which subsystems

**Recommendation**: Focus on consistency and simplification before adding more features. A smaller, more consistent toolset would provide better UX than the current comprehensive but confusing offering.