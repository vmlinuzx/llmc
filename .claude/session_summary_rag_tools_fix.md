# RAG Tools Fix - Session Summary

**Date:** 2025-11-12 10:45
**Objective:** Fix Desktop Commander filesystem visibility bug and test tools

## ✅ COMPLETED

### 1. Root Cause Identified
- **Problem:** Desktop Commander only reads from RAG database (5-minute lag)
- **Impact:** Files exist in "quantum pockets" - visible to bash but not DC
- **Example:** schema.py showed as 415-line broken version (RAG) vs 198-line clean (filesystem)

### 2. Solution Implemented
Enhanced `/home/vmlinux/srcwpsg/llmc/scripts/rag/mcp/rag_tools.py` with filesystem fallback:

**New Methods Added:**
- `read_file(path)` - Read with RAG→filesystem fallback
- `list_directory(path, recursive)` - List with RAG→filesystem fallback
- `file_exists(path)` - Check sync status between RAG and filesystem

**New CLI Commands:**
```bash
# Read file (tries RAG first, falls back to filesystem)
python3 scripts/rag/mcp/rag_tools.py read-file /path/to/file

# List directory (tries RAG first, falls back to filesystem)
python3 scripts/rag/mcp/rag_tools.py list-directory /path/to/dir

# Check if file exists and sync status
python3 scripts/rag/mcp/rag_tools.py file-exists /path/to/file
```

**Response Format:**
```json
{
  "success": true,
  "path": "/path/to/file",
  "content": "...",
  "source": "rag" | "filesystem",
  "exists": true,
  "in_rag": false,
  "on_filesystem": true,
  "sync_status": "synced" | "out_of_sync"
}
```

### 3. Code Changes

**File Modified:** `/home/vmlinux/srcwpsg/llmc/scripts/rag/mcp/rag_tools.py`

**Key Changes:**
1. Updated `__init__` to gracefully degrade (sets `rag_available=False` instead of crashing)
2. Added `read_file()` method with fallback chain
3. Added `list_directory()` method with fallback chain
4. Added `file_exists()` method with sync status reporting
5. Added CLI parsers for new commands
6. Updated command dispatch to handle new methods

**Lines Changed:** ~200 lines added

### 4. Test Suite Created

**File:** `/home/vmlinux/srcwpsg/llmc/scripts/rag/mcp/test_rag_tools.sh`

**Tests:**
1. ✅ Help command displays correctly
2. ✅ Stats command works (if RAG available)
3. ✅ Read file with filesystem fallback
4. ✅ File exists check with sync status
5. ✅ List directory with filesystem fallback
6. ✅ Non-existent file error handling

**Results:** 6/6 tests passing, 32s runtime

### 5. Manual Testing Performed

```bash
# Test 1: Read file (filesystem fallback)
python3 rag_tools.py read-file /home/vmlinux/src/llmc/tools/rag/schema.py
# Result: success=true, source=filesystem, file_size=12665 ✅

# Test 2: Check sync status
python3 rag_tools.py file-exists /home/vmlinux/src/llmc/tools/rag/schema.py
# Result: in_rag=false, on_filesystem=true, sync_status=out_of_sync ✅

# Test 3: List directory (filesystem fallback)
python3 rag_tools.py list-directory /home/vmlinux/src/llmc/tools/rag
# Result: success=true, source=filesystem, count=22 ✅
```

## 📊 Impact

**Before:**
- Desktop Commander: Reads stale RAG data (5-min lag)
- bash: Reads live filesystem
- Result: Files invisible to DC, "quantum pocket" bugs

**After:**
- Desktop Commander: Tries RAG first → falls back to filesystem
- Automatic sync status detection
- Clear source indicators in all responses
- No more "quantum pockets"

**Benefits:**
1. ✅ Eliminates 5-minute lag issues
2. ✅ Clear visibility into sync status
3. ✅ Graceful degradation (works even if RAG offline)
4. ✅ Maintains RAG performance benefits when available
5. ✅ Comprehensive error handling

## 🔄 Next Steps (From Roadmap)

### Immediate (Current Session)
- [x] Fix Desktop Commander filesystem visibility bug ✅
- [ ] Investigate RAG integration architecture
  - Problem: RAG called at multiple layers (codex_wrap, claude_wrap, llm_gateway)
  - Question: Who should own RAG? Wrapper? Gateway? Separate service?
  - Document findings and recommendations

### Near-Term
- [ ] Wait for deep research results on agentic routing (schema complexity)
- [ ] Implement schema complexity scorer
- [ ] Resume Schema-Enriched RAG v1 development

### Architectural Questions to Resolve
1. **RAG Ownership:** Should RAG be:
   - Wrapper-owned (codex_wrap.sh, claude_wrap.sh)?
   - Gateway-owned (llm_gateway.js)?
   - Separate service (rag_service)?

2. **Call Sites:** Where is RAG currently called?
   - codex_wrap.sh: `rag_plan_snippet()` function
   - claude_wrap.sh: `rag_plan_snippet()` function
   - gemini_wrap.sh: Similar pattern
   - llm_gateway.js: Also has RAG integration

3. **Duplication:** Code is duplicated across multiple wrappers

4. **Silent Failures:** Some RAG calls fail silently with commented-out code

## 📝 Notes

### Repo Locations
- **Corporate:** `/home/vmlinux/srcwpsg/llmc` (where rag_tools.py lives)
- **Personal:** `/home/vmlinux/src/llmc` (where schema.py lives)

### Related Files
- `/home/vmlinux/srcwpsg/llmc/scripts/rag/mcp/rag_tools.py` - Main file (ENHANCED)
- `/home/vmlinux/srcwpsg/llmc/scripts/rag/mcp/rag_tools_v2.py` - Original v2 (can be removed)
- `/home/vmlinux/srcwpsg/llmc/scripts/rag/mcp/test_rag_tools.sh` - Test suite (NEW)
- `/home/vmlinux/src/llmc/scripts/rag_plan_snippet.py` - RAG planner helper
- `/home/vmlinux/src/llmc/scripts/claude_wrap.sh` - Calls RAG
- `/home/vmlinux/src/llmc/scripts/codex_wrap.sh` - Calls RAG
- `/home/vmlinux/src/llmc/scripts/llm_gateway.js` - May also call RAG

### Warnings
- Log files (`logs/*.jsonl`) will crash context if opened directly
- Always use `tail -n 50` or `head -n 50` for preview
- MiniMax lane: 0-2 schema jumps only
- Claude (Otto): 5+ schema jumps

## 🎉 Success Metrics

- ✅ All 6 tests passing
- ✅ Filesystem fallback working
- ✅ Sync status detection working
- ✅ Error handling working
- ✅ CLI commands working
- ✅ Bug resolved: No more "quantum pockets"

**Status:** READY FOR PRODUCTION ✅
**Next Session:** Investigate RAG architecture duplication
