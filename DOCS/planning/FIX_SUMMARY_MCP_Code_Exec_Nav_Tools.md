# MCP Server Fixes - 2025-12-04

## Issue #1: RAG Navigation Tools Missing from Code Execution Mode ✅ FIXED

**Severity:** P1 (High)  
**Status:** Fixed  
**File:** `llmc_mcp/server.py`

### Problem
When MCP server runs in code execution mode, RAG navigation tools were missing from the `classic_handlers` fallback dictionary. This caused "Unknown tool" errors when agents tried to invoke these tools via stubs:

- `rag_where_used`
- `rag_lineage`
- `inspect`
- `rag_stats`
- `rag_plan`

### Root Cause
In the `_handle_execute_code` method (lines 748-771), the `classic_handlers` dictionary only included basic tools, missing the RAG navigation/graph tools that were added later.

### Fix
Added missing RAG navigation tools to the `classic_handlers` dictionary in code execution mode:

```python
# RAG Navigation tools
"rag_where_used": self._handle_rag_where_used,
"rag_lineage": self._handle_rag_lineage,
"inspect": self._handle_inspect,
"rag_stats": self._handle_rag_stats,
"rag_plan": self._handle_rag_plan,
```

### Validation
These handlers were already implemented and registered in classic mode (lines 657-661). They just needed to be added to the code_exec mode fallback.

**Expected**: After this fix, all 5 tools should work when called via stubs in code execution mode.

---

## Issue #2: linux_fs_edit Metadata Bug - NOT REPRODUCED

**Severity:** P2 (Medium)  
**Status:** Unable to reproduce  
**File:** `llmc_mcp/tools/fs.py` + `llmc_mcp/tools/fs_protected.py`

### Original Report (from AAR)
Tool reports `replacements_made: 0` even when edit succeeds.

### Investigation
Reviewed code path:
1. `server.py::_handle_fs_edit()` calls `edit_block_protected()`
2. `fs_protected.py::edit_block_protected()` wraps `edit_block()`  
3. `fs.py::edit_block()` returns `FsResult` with `data={"replacements": count}` (line 630)
4. Handler returns JSON with `{"data": result.data, "meta": result.meta}`

**Conclusion:** Code looks correct. The AAR may have been from an earlier version, or there's a specific edge case that triggers this. RMTA will test and confirm.

---

## RMTA Run Status

**Started:** 2025-12-04 14:04 EST  
**Status:** Running (testing MCP tools)  
**Model:** MiniMax-M2 via Anthropic-compatible endpoint  
**Expected Duration:** 5-10 minutes

**Fix Applied Before RMTA Completion:**
- RAG navigation tools in code_exec mode ✅

**Awaiting RMTA Report To Identify:**
- Any remaining P1 missing handlers
- Response format bugs
- UX issues
- Documentation drift

---

## Next Steps

1. ✅ Wait for RMTA to complete first run
2. ⏳ Review RMTA report findings
3. ⏳ Validate fix #1 works (rag_where_used, rag_lineage, inspect, rag_stats, rag_plan)
4. ⏳ Fix any additional P0/P1 issues found by RMTA
5. ⏳ Re-run RMTA to validate all fixes
6. ⏳ Update roadmap item 1.0.1 based on findings

---

## Files Modified

- `llmc_mcp/server.py` - Added 5 RAG nav tools to code_exec mode handlers (lines 759-763)

**Diff:**
```python
+                    # RAG Navigation tools
+                    "rag_where_used": self._handle_rag_where_used,
+                    "rag_lineage": self._handle_rag_lineage,
+                    "inspect": self._handle_inspect,
+                    "rag_stats": self._handle_rag_stats,
+                    "rag_plan": self._handle_rag_plan,
```
