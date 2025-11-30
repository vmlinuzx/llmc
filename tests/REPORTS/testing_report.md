# Testing Report - Modular Embeddings Feature

*Conducted by ROSWAAL L. TESTINGDOM, Margrave of the Border Territories*
*Testing completed: 2025-11-28*
*Branch: feature/modular-embeddings*

---

## Executive Summary

**Overall Assessment:** *The engineering peasentry has managed to produce something that mostly works, though with the usual suspects of minor infestations.*

**Critical Findings:**
- ✅ 1 **CRITICAL FAILURE**: Missing test data file breaks search evaluation test
- ⚠️  **MEDIUM ISSUES**: Lint/format violations and type checking problems
- ✅ **GOOD**: Profile system works, database migration successful, error handling robust

**Test Results:**
- Unit tests: **4 passed** (test_embeddings_unit.py)
- Behavior tests: **4 passed** (test_embeddings_behavior.py)
- RAG integration tests: **87 passed, 30 skipped, 1 failed**
- Static analysis: **2 formatting violations, 2 type errors, import sorting issues**

---

## 1. Scope & Context

This feature introduces a **modular embedding system** with profile-based configuration, replacing the previous single-provider approach. Key changes:

- Profile-based embedding configuration (docs, code, cheap, test profiles)
- Database schema migration to support multiple profiles
- New EmbeddingManager and EmbeddingProvider architecture
- Three providers: Hash, SentenceTransformer, Ollama

**Files Modified:** 7 files (669 insertions, 227 deletions)

---

## 2. Environment & Setup

**Python Version:** 3.12.3
**Virtual Environment:** ✅ Available at `/home/vmlinux/src/llmc/.venv`
**Test Framework:** pytest 9.0.1
**Dependencies:** ⚠️ Missing `textual` module breaks analytics tests

### Setup Verification
- ✅ Python interpreter accessible
- ✅ Virtual environment functional
- ✅ All embedding-related dependencies present
- ❌ `textual` module missing (impacts TUI tests)

**Verdict:** *The peasants can run the core functionality, though some optional features are broken.*

---

## 3. Static Analysis Results

### Ruff Linting
**Command:** `ruff check tools/rag/embeddings.py tools/rag/embedding_manager.py tools/rag/embedding_providers.py`

**Issues Found:**
```
I001  Import block is un-sorted or un-formatted (embedding_manager.py:1)
UP035  Import from collections.abc instead of typing (embedding_manager.py:6)
Would reformat: tools/rag/embedding_manager.py, tools/rag/embeddings.py
```

**Verdict:** *The code formatting peasants need to clean up their import blocks.*

### Type Checking (mypy)
**Command:** `mypy tools/rag/embeddings.py`

**Issues Found:**
```
tools/rag/embedding_providers.py:128: error: Cannot assign to a type [misc]
tools/rag/embedding_providers.py:210: error: Library stubs not installed for "requests" [import-untyped]
```

**Verdict:** *Missing type stubs for requests library and a type assignment error.*

---

## 4. Test Suite Results

### 4.1 Unit Tests - Embeddings Core

**Command:** `pytest tests/test_embeddings_unit.py -v`

```
tests/test_embeddings_unit.py ....                                       [100%]
4 passed in 0.12s
```

**Tests:**
- ✅ `test_hash_backend_is_deterministic` - Hash embeddings are deterministic
- ✅ `test_formatters_apply_prefixes` - Prefixes applied correctly
- ✅ `test_hash_backend_respects_dimension` - Vector dimensions correct
- ✅ `test_build_embedding_backend_hash_override` - Factory creates correct backend

**Verdict:** *Unit tests are suspiciously green. Probed extensively with edge cases - all passed.*

### 4.2 Behavior Tests

**Command:** `pytest tests/test_embeddings_behavior.py -v`

```
tests/test_embeddings_behavior.py ....                                   [100%]
4 passed in 0.03s
```

**Tests:**
- ✅ `test_hash_backend_normalization` - L2 normalization works correctly
- ✅ `test_factory_selects_hash_vs_manager` - Factory chooses correct backend
- ✅ `test_hash_backend_empty_input` - Empty inputs handled gracefully
- ✅ `test_large_dimension` - Large dimensions (1024) work correctly

**Verdict:** *All behavioral tests passed, including edge cases.*

### 4.3 RAG Integration Tests

**Command:** `pytest tools/rag/tests/ -v --tb=short`

```
collected 118 items
87 passed, 30 skipped, 1 failed
```

**❌ CRITICAL FAILURE FOUND:**

```
FAILED tools/rag/tests/test_search_eval_canary.py::test_search_eval_harness_runs_and_prefers_rag

FileNotFoundError: [Errno 2] No such file or directory:
'DOCS/RAG_NAV/P9_Search/canary_queries.jsonl'
```

**Analysis:** This test expects a file `canary_queries.jsonl` that doesn't exist in the repository. This is a **real bug** - the test setup is incomplete.

**Impact:** HIGH - Search evaluation functionality cannot be tested or used.

**Skipped Tests:** 30 tests marked as "not yet implemented" (feature flags/incomplete features)

**Verdict:** *The core RAG functionality works, but search evaluation is broken.*

---

## 5. Behavioral & Edge Testing

### 5.1 Hash Embedding Backend Tests

**Test Case:** Edge inputs
```python
# Empty string
empty_vecs = backend.embed_passages([''])
# Result: ✅ Succeeds, returns valid vector

# Very long string (10,000 chars)
long_vecs = backend.embed_passages(['x' * 10000])
# Result: ✅ Succeeds, returns correct dimension vector
```

**Verdict:** *Hash backend handles edge cases robustly.*

### 5.2 Configuration Error Handling

**Test Case:** Invalid profile configurations

1. **Missing provider:**
   - Input: `{'model': 'test', 'dimension': 64}`
   - Result: ✅ `EmbeddingConfigError: Profile 'test_profile' is missing 'provider'`

2. **Unknown provider:**
   - Input: `{'provider': 'nonexistent', 'model': 'test', 'dimension': 64}`
   - Result: ✅ `EmbeddingConfigError: Profile 'test_profile' references unknown provider 'nonexistent'`

3. **Negative dimension:**
   - Input: `{'provider': 'hash', 'model': 'test', 'dimension': -10}`
   - Result: ✅ `EmbeddingConfigError: Profile 'test_profile' has negative dimension -10`

**Verdict:** *Error handling is excellent - all invalid configurations are caught.*

### 5.3 Profile System

**Test Case:** Multiple profiles
```python
profiles = manager.list_profiles()
# Result: ['docs', 'code', 'cheap', 'test']

default = manager.get_default_profile()
# Result: 'docs'
```

**Verdict:** *Profile system functions correctly.*

### 5.4 Provider Factory

**Test Case:** Backend selection
```python
hash_backend = build_embedding_backend("hash-emb-v1", dim=16)
# Result: ✅ HashEmbeddingBackend

manager_backend = build_embedding_backend("some-model", dim=384)
# Result: ✅ ManagerEmbeddingBackend
```

**Verdict:** *Factory correctly chooses backend based on model type.*

---

## 6. Database Migration

**Test:** Legacy schema → Profile-aware schema migration

**Process:**
1. Created database with old schema (no profile columns)
2. Opened with new Database class
3. Verified migration

**Results:**
- ✅ Old schema converted to new schema
- ✅ Profile column added to both `embeddings_meta` and `embeddings` tables
- ✅ Existing data preserved
- ✅ New profile-aware inserts work correctly

**Verdict:** *Migration is robust and preserves data.*

---

## 7. Documentation & Configuration Issues

### 7.1 Config File (llmc.toml)

**Issue Found:**
```toml
[embeddings.profiles.test]
provider = "hash"
dimension = 64

# ase-v2"  # or "hash-emb-v1" for deterministic CPU-only testing
gpu_min_free_mb = 1536
```

Line 25 has a broken comment `# ase-v2"` which appears to be a remnant from the old configuration format.

**Severity:** LOW - Cosmetic issue but shows incomplete cleanup.

### 7.2 Missing Test Data

The test `test_search_eval_harness_runs_and_prefers_rag` requires a file:
```
DOCS/RAG_NAV/P9_Search/canary_queries.jsonl
```

This file does not exist in the repository, causing the test to fail.

**Severity:** HIGH - Missing required test asset.

---

## 8. Most Important Bugs (Prioritized)

### 1. Missing Test Data File
- **Severity:** CRITICAL
- **Area:** Testing
- **File:** `tools/rag/tests/test_search_eval_canary.py`
- **Issue:** Test expects `DOCS/RAG_NAV/P9_Search/canary_queries.jsonl` which doesn't exist
- **Impact:** Search evaluation functionality cannot be tested or validated
- **Repro:** Run `pytest tools/rag/tests/test_search_eval_canary.py::test_search_eval_harness_runs_and_prefers_rag`
- **Fix:** Create the missing test data file or update test to use existing data

### 2. Type Checking Errors
- **Severity:** MEDIUM
- **Area:** Type Safety
- **File:** `tools/rag/embedding_providers.py`
- **Issue:** Cannot assign to a type (line 128), missing type stubs for requests
- **Impact:** Reduced type safety, potential runtime errors
- **Fix:** Install `types-requests` package, fix type assignment

### 3. Code Formatting Issues
- **Severity:** LOW
- **Area:** Code Quality
- **Files:** `tools/rag/embedding_manager.py`, `tools/rag/embeddings.py`
- **Issue:** Unsorted imports, should use `collections.abc` instead of `typing`
- **Impact:** Code style violations
- **Fix:** Run `ruff format` to fix formatting

### 4. Broken Configuration Comment
- **Severity:** LOW
- **Area:** Configuration
- **File:** `llmc.toml`
- **Issue:** Line 25 has incomplete comment `# ase-v2"`
- **Impact:** Cosmetic, shows incomplete refactoring
- **Fix:** Remove or complete the comment

---

## 9. Coverage & Limitations

### Areas Tested
- ✅ Hash embedding backend (deterministic, edge cases)
- ✅ Backend factory selection logic
- ✅ Profile system (list, default, creation)
- ✅ Provider configuration error handling
- ✅ Database migration (legacy → profile-aware)
- ✅ Embedding normalization
- ✅ Dimension handling (small to 1024)

### Areas Not Tested
- ⚠️ SentenceTransformer provider (requires model download)
- ⚠️ Ollama provider (requires running Ollama server)
- ⚠️ Real embedding generation with actual models
- ⚠️ TUI/Analytics screens (textual module missing)
- ⚠️ Search evaluation harness (missing test data)

### Limitations
- Tests rely on hash provider for fast, deterministic results
- External dependencies (Ollama, SentenceTransformers) not tested
- Analytics/TUI tests blocked by missing `textual` dependency

---

## 10. Recommendations

### Immediate Actions (Critical)
1. **Create missing test data file** for search evaluation test
2. **Install `types-requests`** for type checking
3. **Install `textual` module** to enable TUI tests

### Short Term (Medium)
1. **Fix type errors** in embedding_providers.py
2. **Run `ruff format`** to fix import sorting and formatting
3. **Add integration tests** for SentenceTransformer and Ollama providers

### Long Term (Low)
1. **Complete skipped tests** (30 tests marked "not yet implemented")
2. **Add performance tests** for large-scale embedding operations
3. **Add documentation** for the new profile system

---

## Conclusion

The modular embeddings feature is **functionally sound** with a robust architecture. The profile system works correctly, database migration preserves data, and error handling is excellent. However, the **missing test data file** is a critical issue that must be addressed before this can be considered production-ready.

The engineering peasentry has done **adequate work**, though they should review the static analysis violations and complete the test setup. With the critical test data file created, this feature would be ready for deployment.

**Final Verdict:** *Not quite ready for the castle, but not entirely worthy of the dungeon either. Fix the test data and submit again.*

---
*End of Report*
