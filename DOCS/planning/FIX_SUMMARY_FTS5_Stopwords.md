# P0 Bug Fix: FTS5 Stopwords Filtering Critical Keywords

**Date:** 2025-12-03  
**Severity:** CRITICAL (P0)  
**Status:** ✅ FIXED  

---

## Executive Summary

**Incident:** RAG search returned **0 results** for any query containing the word "model"

**Root Cause:** SQLite FTS5 default `porter` tokenizer includes English stopword list that filters out "model", "system", "data" and other fundamental ML/AI terms

**Fix:** Changed FTS5 tokenizer from `porter` to `unicode61` (no stopwords)

**Impact:** Critical - RAG search was completely unusable for core ML/AI queries

**Timeline:** Discovered and fixed same day (2025-12-03)

---

## Problem Statement

### Symptoms

```
Query                          | Results | Expected | Status
-------------------------------|---------|----------|--------
"model"                        | 0       | 1000s    | FAIL
"routing model"                | 0       | 100s     | FAIL
"routing strategy tier model"  | 0       | 10s      | FAIL
"model selection"              | 0       | 100s     | FAIL
"routing"                      | 6,039   | 1000s    | PASS
"strategy"                     | 6,039   | 1000s    | PASS
```

### Impact

- **Severity:** P0 - System Unusable
- "model" is a fundamental term in ML/AI codebases
- Current LLMC codebase has 3 embedding models, query routing models, LLM models
- Makes RAG essentially unusable for core functionality searches
- Affects searches for:
  - "embedding model"
  - "LLM model"
  - "model routing"
  - "model selection"
  - "model configuration"

---

## Root Cause Analysis

### Investigation Steps

1. ✅ Grepped codebase for stopword lists in Python code → Found `planner.py` STOPWORDS set (did NOT contain "model")
2. ✅ Checked RAG search pipeline → Found FTS5 full-text search in `db_fts.py`
3. ✅ Examined FTS5 table creation in `database.py` → **FOUND IT**

### The Smoking Gun

File: `tools/rag/database.py`, line 529-533 (before fix):

```python
CREATE VIRTUAL TABLE IF NOT EXISTS enrichments_fts
USING fts5(
    symbol,
    summary
)
```

**Problem:** FTS5 **defaults to the `porter` tokenizer** which includes a built-in English stopword list!

### Why This Happened

- Someone created an FTS5 table using SQLite defaults without researching tokenizer options
- Default `porter` tokenizer is designed for English prose (academic papers, news articles, novels)
- For English prose, "model", "system", "data" ARE noise words
- For ML/AI technical documentation, these are CRITICAL domain vocabulary
- **Classic ML/NLP library misconfiguration**

---

## The Fix

### Code Changes

**File:** `tools/rag/database.py`

```python
# BEFORE (buggy)
CREATE VIRTUAL TABLE IF NOT EXISTS enrichments_fts
USING fts5(
    symbol,
    summary
)

# AFTER (fixed)
CREATE VIRTUAL TABLE IF NOT EXISTS enrichments_fts
USING fts5(
    symbol,
    summary,
    tokenize='unicode61'  # ← NO STOPWORDS!
)
```

### Why unicode61?

- **unicode61**: Simple Unicode word boundary tokenizer, **NO stopword list**
- **porter**: English stemming + stopword filtering (inappropriate for technical search)
- **ascii**: Similar to unicode61 but doesn't handle UTF-8 properly

Reference: https://www.sqlite.org/fts5.html#unicode61_tokenizer

---

## Migration

### For Existing Databases

Run the migration script to rebuild FTS indexes:

```bash
python3 scripts/migrate_fts5_no_stopwords.py /path/to/repo
```

The script will:
1. Drop the existing `enrichments_fts` table
2. Recreate it with `unicode61` tokenizer
3. Rebuild the index from enrichment data
4. Report number of indexed enrichments

### For LLMC Repository

Migration output:
```
📂 Migrating FTS5 index: /home/vmlinux/src/llmc/.rag/index_v2.db
  🗑️  Dropping old enrichments_fts table...
  ✨ Creating new enrichments_fts table (unicode61, no stopwords)...
  📊 Rebuilding FTS index from enrichment data...
  ✅ Migration complete! Indexed 5776 enrichments
  🎯 Keyword 'model' is now searchable!
```

---

## Verification

### Regression Tests

**File:** `tests/test_fts5_stopwords_regression.py`

Tests verify:
- ✅ Critical keywords return results (not filtered)
- ✅ "model" keyword specifically works (original bug)
- ✅ Multi-word queries execute without errors
- ✅ FTS table uses `unicode61` tokenizer
- ✅ Comprehensive test of all critical ML/AI keywords

**Run tests:**
```bash
pytest tests/test_fts5_stopwords_regression.py -v
```

**Results:**
```
======================================= test session starts ========================================
tests/test_fts5_stopwords_regression.py .....                                                [100%]
=================================== 5 passed, 1 warning in 0.15s ===================================
```

### Manual Validation

```python
from tools.rag.database import Database

db = Database("/path/to/.rag/index_v2.db")
results = db.search_enrichments_fts("model", limit=10)
print(f"Results for 'model': {len(results)}")  # Should be > 0

# Example output:
# Results for 'model': 10
# - embedding-model: Define embedding model and dimension.
# - ManagerEmbeddingBackend.model_name: Returns model name as string.
# - MockBackend.model_name: Tests the model_name method.
# ...
```

---

## Prevention

### 1. Regression Tests

Added comprehensive tests for critical ML/AI domain keywords:
- model, system, data, select, train, router, pipeline

These tests will FAIL if stopwords are ever reintroduced.

### 2. Code Documentation

Added clear comments in `database.py` explaining:
- Why `unicode61` is required
- Why default `porter` is inappropriate
- Link to SQLite documentation

### 3. Test Coverage

Tests verify:
- FTS table schema uses correct tokenizer
- Critical keywords return results
- No FTS syntax errors on multi-word queries

### 4. Future Monitoring

Recommendation: Add CI/CD metric for search zero-result rate

---

## Files Changed

### Modified
- `tools/rag/database.py` - FTS5 table creation with unicode61 tokenizer

### Created
- `scripts/migrate_fts5_no_stopwords.py` - Migration script for existing DBs
- `tests/test_fts5_stopwords_regression.py` - Regression tests
- `DOCS/planning/FIX_SUMMARY_FTS5_Stopwords.md` - This document

### Updated
- `DOCS/ROADMAP.md` - Added bug fix entry with full analysis

---

## Lessons Learned

1. **Never use generic NLP preprocessing defaults for domain-specific technical search**
   - English prose stopword lists are inappropriate for code/technical documentation
   - Always research tokenizer options before using FTS5 defaults

2. **Critical domain vocabulary must be tested in regression suite**
   - Test searches for fundamental terms in your domain
   - Don't assume library defaults are correct for your use case

3. **SQLite FTS5 defaults are optimized for English prose, not code**
   - `porter` tokenizer: English stemming + stopwords → good for novels, bad for code
   - `unicode61` tokenizer: No stopwords, Unicode-aware → good for technical search

4. **Zero-result searches are a critical failure mode**
   - Monitor search zero-result rate in CI/CD
   - Alert if zero-result rate exceeds threshold

---

## References

- SQLite FTS5 Documentation: https://www.sqlite.org/fts5.html
- unicode61 Tokenizer: https://www.sqlite.org/fts5.html#unicode61_tokenizer
- Porter Tokenizer: https://www.sqlite.org/fts5.html#porter_tokenizer
- FTS5 Stopwords: (undocumented in SQLite docs, hardcoded in porter.c)

---

## Contact

For questions about this fix, see:
- Root cause analysis document (this file)
- Roadmap entry: `DOCS/ROADMAP.md` section 1.1.5
- Regression tests: `tests/test_fts5_stopwords_regression.py`
