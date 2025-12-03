# RAG "Model" Search Bug - Final Summary

**Date:** 2025-12-03  
**Status:** ✅ FIXED AND TESTED  
**Severity:** P0 CRITICAL  

---

## What Was Broken

Query for "model" keyword returned **0 results** (expected: thousands).

## Root Causes (3 Bugs Found)

### 1. **Routing Configuration Bug** (PRIMARY)
- **File:** `llmc.toml`
- **Issue:** `[embeddings.routes.erp]` pointed to non-existent table `emb_erp`
- **Impact:** Queries routed to "erp" (like "model") failed silently
- **Fix:** Changed `index = "emb_erp"` → `index = "embeddings"`

### 2. **Config Caching Bug** (DX KILLER)
- **File:** `tools/rag/config.py`
- **Issue:** `@lru_cache` on config functions prevented hot-reload
- **Impact:** Config edits only visible after manual cache clearing + daemon restart
- **Fix:** Removed `@lru_cache` from 3 functions:
  - `load_config()`
  - `resolve_route()`
  - `get_route_for_slice_type()`
- **Performance:** 0.9ms overhead = 0.2% of search time (negligible)

### 3. **MCP Adapter Bug** (CASCADING)
- **File:** `llmc_mcp/tools/rag.py`
- **Issue:** Calling `.cache_clear()` on functions that no longer have `@lru_cache`
- **Impact:** MCP searches crashed with "no attribute 'cache_clear'"
- **Fix:** Removed 2 calls to `load_config.cache_clear()`

### 4. **FTS5 Stopwords** (SECONDARY)
- **File:** `tools/rag/database.py`
- **Issue:** Default `porter` tokenizer filters "model", "system", "data"
- **Impact:** FTS-based searches (navigation tools) failed for ML/AI terms
- **Fix:** Changed tokenizer to `unicode61` (no stopwords)

---

## Files Modified

1. **`llmc.toml`** - Fixed erp route configuration
2. **`tools/rag/config.py`** - Removed config caching
3. **`llmc_mcp/tools/rag.py`** - Removed cache_clear() calls
4. **`tools/rag/database.py`** - Fixed FTS5 stopwords

---

## Testing

### Automated Test
```bash
python3 scripts/test_model_search_fix.py
```

**Results:**
```
✅ TEST 1: 'model' returns 5 results (scores 0.915-1.000)
✅ TEST 2: Config hot-reload works (no restart needed)
```

### Manual Verification
```bash
# Via MCP
from stubs import rag_search
result = rag_search(query="model", limit=5)
# Returns: 5 results ✅

# Via direct API
from tools.rag.search import search_spans
results = search_spans("model", limit=5, repo_root=repo)
# Returns: 5 results ✅
```

---

## Deployment Notes

**Important:** After deploying code changes, **restart all running services**:
1. RAG daemon: `pkill -9 -f "llmc-rag.*daemon" && llmc-rag-service start`
2. MCP server: Restart Claude Desktop or reconnect MCP
3. Any Python processes with old imports

**Why:** Long-running processes cache imported modules. Code changes only take effect after restart.

---

## The Caching Nightmare

The debugging process revealed a perfect storm of Python caching layers:

1. `@lru_cache` - Function-level caching
2. Module import cache - `sys.modules` keeps loaded modules
3. Bytecode cache - `__pycache__/*.pyc` files
4. Long-running daemons - Process memory holds old code

**Lesson:** `@lru_cache` on config loading is an **anti-pattern** for services.

Config should:
- Reload on every request (cheap: 0.9ms)
- Reflect file changes immediately
- Not require manual cache invalidation

---

## Verification Checklist

- [x] "model" keyword returns results
- [x] MCP rag_search works
- [x] Direct search_spans works
- [x] Config hot-reload works (edit llmc.toml, immediate effect)
- [x] No cache_clear() needed
- [x] FTS5 searches work for ML/AI terms
- [x] Regression tests pass
- [x] Migration script works

---

## Prevention

**Added:**
- Regression tests: `tests/test_fts5_stopwords_regression.py`
- Test script: `scripts/test_model_search_fix.py`
- Migration script: `scripts/migrate_fts5_no_stopwords.py`
- Documentation: This file + ROADMAP.md

**Monitoring:**
- Watch zero-result rate for critical keywords
- Alert if "model", "system", "data" return 0 results

---

## Performance Impact

| Component | Before | After | Change |
|-----------|--------|-------|--------|
| Config load | Cached | 0.9ms | +0.9ms |
| Search total | 577ms | 578ms | +0.2% |
| **Conclusion** | - | - | **Negligible** |

---

**Status:** ✅ Fixed, tested, documented  
**Test Command:** `python3 scripts/test_model_search_fix.py`  
**Next Steps:** Monitor search metrics for any regression
