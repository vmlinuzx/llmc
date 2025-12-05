# After Action Review - MCP Server Live Testing
**Date:** 2025-12-04  
**Tester:** Claude (Antigravity Interface)  
**Context:** First live agent test of LLMC MCP Server through Antigravity  
**Repo:** vmlinuzx/llmc  

---

## Executive Summary

Conducted comprehensive live testing of the LLMC MCP server through a real agent interface (Antigravity). This revealed critical gaps between **advertised capabilities** and **actual implementations**, plus UX issues that would be invisible to traditional unit tests.

**Key Finding:** Approximately **35% of advertised MCP tools are not implemented** (stubs only), and **documentation/prompts assume environment state** that doesn't always hold (incorrect paths).

**Severity:** P1 - These gaps create a poor developer experience and erode trust in the tool ecosystem.

---

## Context and Motivation

### The Problem
Traditional MCP server testing (unit tests, manual CLI invocation) cannot detect:
1. **Agent UX issues** - Prompts that confuse LLMs due to incorrect path assumptions
2. **Tool discovery failures** - Stubs listed but handlers missing
3. **Response format inconsistencies** - Tools that succeed but return misleading metadata

### The Approach
Used an LLM agent (Claude via Antigravity) to:
1. Navigate the MCP server using only the `00_INIT` bootstrap instructions
2. Systematically test each advertised stub
3. Report discrepancies between expected and actual behavior

This mirrors how a real user (human or agent) would experience the system.

---

## Testing Methodology

### Tools Tested
Systematically exercised stubs from all categories advertised in `BOOTSTRAP_PROMPT`:

**Categories:**
- RAG Tools (search, query, graph traversal)
- File System (read, write, edit, delete)
- Process Management (list, kill, snapshot, REPL)
- Command Execution (run_cmd, te_run)

**Test Approach:**
For each tool:
1. Read the stub signature (if discovery worked)
2. Execute a realistic use case
3. Verify the response structure and data quality
4. Document discrepancies

---

## Findings

### 1. Documentation/UX Issues

#### 1.1 Incorrect Path in Bootstrap Prompt ⚠️ CRITICAL
**Severity:** P1  
**Area:** Agent Onboarding  

**Issue:**
The `EXECUTE_CODE_TOOL` description instructs agents to:
```
1. Use list_dir('.llmc/stubs/') to see available tools
```

This assumes the server's CWD is the repo root. In practice:
- Antigravity MCP config had CWD = `/home/vmlinux`
- Actual stubs location: `/home/vmlinux/src/llmc/.llmc/stubs/`
- Result: Initial discovery failed with "outside allowed roots" error

**Impact:**
- Agent cannot bootstrap correctly
- Wastes time debugging path issues
- Creates impression that the system is broken

**Remediation:**
✅ **FIXED** - Changed prompt to:
```
1. Use list_dir('<repo_root>/.llmc/stubs/') to see available tools
```

#### 1.2 Missing Summary Fields in RAG Results ⚠️
**Severity:** P2  
**Area:** Data Quality  

**Issue:**
`rag_query` sometimes returns results where `summary` field is `None`:
```python
{'rank': 2, 'symbol': 'has_field', 'score': 0.9939, 'summary': None}
```

**Impact:**
- Agents must defensively check for `None` before string operations
- Degrades agent code quality (extra null checks)

**Remediation:**
- **Option 1:** Guarantee non-null summaries (use placeholder like "No summary available")
- **Option 2:** Update schema documentation to clarify optional fields

---

### 2. Not Implemented Tools (Advertised but Non-Functional)

#### 2.1 Graph-Based RAG Tools ❌
**Severity:** P1  
**Tools:** `rag_where_used`, `rag_lineage`, `rag_stats`, `inspect`  

**Issue:**
All return `{"error": "Unknown tool: <name>"}` despite being:
- Listed in `BOOTSTRAP_PROMPT` stubs
- Defined in `TOOLS` array in `server.py`
- Having generated stub files in `.llmc/stubs/`

**Root Cause:**
Handlers not registered in `tool_handlers` dict (neither classic nor code_exec mode).

**Impact:**
- Agents attempt to use these tools and fail
- No graph-based dependency analysis available for agents
- Breaks advanced RAG features advertised in docs

**Test Evidence:**
```python
from stubs import rag_where_used
results = rag_where_used(symbol="EnrichmentPipeline", limit=10)
# → {"error": "Unknown tool: rag_where_used"}
```

#### 2.2 Linux Process Management Tools ❌
**Severity:** P2  
**Tools:** `linux_proc_list`, `linux_sys_snapshot`, `linux_proc_start/send/read/stop`  

**Issue:**
All tools return empty/null data:
```python
linux_proc_list(max_results=5)
# → {"data": []}  # 0 processes on a running system

linux_sys_snapshot()
# → {"data": {"cpu_percent": "N/A", "mem_percent": "N/A", ...}}
```

**Impact:**
- Agents cannot monitor system resources
- No REPL/interactive process support
- `L2` and `L3` LinuxOps features are non-functional

**Root Cause:**
Handlers exist but return stub data (likely placeholder implementations).

---

### 3. Response Format Bugs

#### 3.1 `linux_fs_edit` Incorrect Replacement Count ⚠️
**Severity:** P2  
**Tool:** `linux_fs_edit`  

**Issue:**
Tool successfully performed text replacement but reported:
```python
{'data': {'replacements_made': 0}, ...}
```

Verification via `read_file` confirmed the edit was applied.

**Impact:**
- Agents cannot programmatically verify edit success
- May trigger unnecessary retries

**Test Evidence:**
```python
# Before: "MCP test write at ..."
linux_fs_edit(path=..., old_text="MCP test", new_text="MCP successful test")
# → reports 0 replacements

read_file(path=...)
# → "MCP successful test write at ..." (edit was applied!)
```

#### 3.2 `stat` Tool Returns Minimal Metadata ℹ️
**Severity:** P3  
**Tool:** `stat`  

**Issue:**
Returns `type` but no `size_bytes`, `modified_iso`, or other typical stat fields.

**Impact:**
- Limited utility compared to Unix `stat`
- May be intentional (low context overhead), but undocumented

---

### 4. Working Tools ✅

**The following tools work correctly and reliably:**

| Category | Tool | Status |
|----------|------|--------|
| RAG | `rag_query` | ✅ Works (minor data quality issues) |
| File System | `read_file` | ✅ Works |
| File System | `list_dir` | ✅ Works |
| File System | `linux_fs_write` | ✅ Works (returns SHA256) |
| File System | `linux_fs_delete` | ✅ Works |
| File System | `linux_fs_edit` | ⚠️ Works (incorrect response metadata) |
| Commands | `run_cmd` | ✅ Works |

---

## Impact Analysis

### Agent Trust and Productivity
**Current State:**
- Agent tries `rag_where_used` → fails → wastes tokens and time
- Agent follows bootstrap instructions → path error → confusion
- Agent edits file → sees "0 replacements" → unnecessary retry

**Result:**
- Increased latency in agent workflows
- Degraded agent "confidence" in tool ecosystem
- Higher token costs due to error recovery

### Developer Experience
**Current State:**
- Developer reads `BOOTSTRAP_PROMPT` → sees 23+ tools available
- Developer attempts to use graph features → discovers they're stubs
- Developer loses ~30 minutes debugging path issues

**Result:**
- Erosion of trust in MCP server capabilities
- Unclear which tools are "production ready" vs "experimental"

---

## Recommendations

### P1 - Immediate Actions

1. **Update Tool Advertising**
   - Remove non-implemented tools from `BOOTSTRAP_PROMPT` stub list
   - OR add clear markers: `(experimental)`, `(not implemented)`
   - Update `README` / docs to clarify feature status

2. **Fix Path Documentation**
   - ✅ Already fixed in this session
   - Add validation: MCP server should log actual stubs path on startup

3. **Implement Missing Handlers**
   - Add handlers for graph tools OR remove from `TOOLS` array
   - If stubs are intentional, add error messages explaining why

### P2 - Near-Term Improvements

4. **Add MCP Server Health Check**
   - `health()` tool should verify:
     - All advertised tools have handlers
     - Stubs directory is accessible
     - No orphaned tool definitions

5. **Fix Response Metadata Bugs**
   - `linux_fs_edit` should return correct `replacements_made`
   - RAG tools should guarantee non-null `summary` fields

6. **Process Management Tools**
   - Either implement `linux_proc_*` tools properly
   - OR document them as "planned" and remove from bootstrap

### P3 - Strategic

7. **Automated MCP Testing Harness** (see HLD_Ruthless_MCP_Testing_Agent.md)
   - Systematically test all tools through agent interface
   - Catch regressions in advertised vs actual capabilities
   - Validate prompt accuracy against runtime state

---

## Lessons Learned

### What Went Well ✅
1. **Code execution mode works** - The stub pattern reduces context overhead
2. **Core tools are solid** - File ops and RAG search are reliable
3. **Live testing revealed UX issues** - Traditional tests would have missed these

### What Didn't Go Well ❌
1. **Tool discovery was confusing** - Incorrect path in prompt wasted time
2. **Many advertised tools don't work** - Undermines user trust
3. **No automated validation** - Stale docs/prompts drift from implementation

### Action Items
- [ ] Update `BOOTSTRAP_PROMPT` and `EXECUTE_CODE_TOOL` description (✅ done in this session)
- [ ] Remove non-implemented tools from advertising OR implement handlers
- [ ] Create automated MCP testing agent (HLD in separate doc)
- [ ] Add MCP server startup validation (logs/warns about missing handlers)

---

## Conclusion

This AAR demonstrates the **critical value of agent-based testing** for MCP servers. Traditional unit tests verify that tools *can* be called; agent testing verifies that tools are **discoverable, usable, and aligned with documentation**.

**Next Steps:**
1. Address P1 fixes (remove false advertising, fix path docs)
2. Implement **Ruthless MCP Testing Agent** to prevent regression
3. Establish policy: tools in `BOOTSTRAP_PROMPT` must have working handlers

**Quote:**
> "The best test is the one that runs continuously in the environment where failure hurts most."  
> — This is that test.
