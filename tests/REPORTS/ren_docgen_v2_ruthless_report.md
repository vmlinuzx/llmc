# Testing Report - Docgen v2

## 1. Scope
- Repo / project: llmc
- Feature / change under test: Docgen v2 (Deterministic RAG-aware documentation generation)
- Commit: 9617bf891cd6f9218ca5fca9285ac6fe55de2a37
- Date: 2025-12-03

## 2. Summary
- **Overall assessment:** **SIGNIFICANT FAILURES**. The "Production Ready" claim is rejected.
- **Key risks:**
    - Application crashes immediately on install due to missing dependencies.
    - Docgen functionality is partially broken due to schema mismatches.
    - Configuration for storage paths is ignored, leading to "Database not found" errors.

## 3. Environment & Setup
- **Initial State:** `llmc` command not found.
- **Dependency Failure:** `ModuleNotFoundError: No module named 'toml'` prevented any `llmc docs` command from running.
    - **Fix applied:** `pip install toml` in `.venv`.
    - **Note:** `pyproject.toml` lists `tomli` but code imports `toml`.

## 4. Static Analysis
- **Ruff:** 640 errors found. (Claim "Fixed all ruff linting errors" is FALSE).
- **Mypy:** 16 errors found. `no-any-return` still present in `tools/rag/indexer.py`.

## 5. Test Suite Results
- **Initial Run:** CRITICAL FAILURE (Missing `mcp`, missing `toml`).
- **After Fix:** 1516 passed, 119 skipped.
    - **Suspicious:** `llmc_mcp/test_smoke.py` is SKIPPED. Smoke tests should never be skipped.

## 6. Behavioral & Edge Testing

### Operation: `llmc docs generate`
- **Scenario:** Happy path (generate docs for `llmc/docgen/types.py`)
- **Status:** **FAIL** (initially), **PARTIAL SUCCESS** (after workarounds)
- **Issues:**
    1.  **Path Resolution Bug:** The tool fails to find the RAG database. It hardcodes `.llmc/rag/index_v2.db` and ignores `llmc.toml`'s `[storage] index_path`.
        - *Workaround:* Created symlink `.llmc/rag/index_v2.db -> .rag/index_v2.db`.
    2.  **Graph Context Schema Mismatch:** Logged error `Failed to build graph context: 'list' object has no attribute 'items'`.
        - *Cause:* `rag_graph.json` contains `"entities": [...]` (List), but `graph_context.py` treats it as a Dict (`.items()`).
        - *Impact:* Documentation is generated WITHOUT graph context (entity relationships).

### Operation: `llmc docs status`
- **Scenario:** Check status
- **Status:** PASS (after workarounds).

## 7. Documentation & DX Issues
- **DX:** The error message for enabling docgen in config is helpful.
- **DX:** The error message for missing RAG DB is misleading because it points to a hardcoded path that the user cannot change via config.

## 8. Most Important Bugs (Prioritized)

1.  **Title:** Missing `toml` dependency causes immediate crash
    - **Severity:** **Critical**
    - **Area:** Packaging / Dependencies
    - **Observed:** `ModuleNotFoundError: No module named 'toml'`
    - **Expected:** Application runs out of the box.

2.  **Title:** Docgen ignores `index_path` configuration
    - **Severity:** **High**
    - **Area:** CLI / Configuration
    - **Observed:** Looks for `.llmc/rag/index_v2.db` regardless of `llmc.toml`.
    - **Expected:** Respects `[storage] index_path`.

3.  **Title:** Graph Context failure due to List vs Dict schema mismatch
    - **Severity:** **High**
    - **Area:** Docgen / Graph
    - **Observed:** `AttributeError: 'list' object has no attribute 'items'` in `graph_context.py`.
    - **Evidence:** `rag_graph.json` has list of entities; code expects dict.

4.  **Title:** Linting and Type errors persist despite claims
    - **Severity:** Low
    - **Area:** Quality
    - **Observed:** 640 Ruff errors, 16 Mypy errors.

## 9. Coverage & Limitations
- Did not test `llmc docs generate --all` due to time constraints and the blocking bugs.
- Assumed `rag_graph.json` format was correct (it's the code that's likely "wrong" relative to the data, or vice versa).

## 10. Ren's Vicious Remark
"100% pass rate"? Only if you count "crashing before the tests start" as a passing grade in the School of Wishful Thinking. Your "Production Ready" code tripped over its own shoelaces (dependencies) and then face-planted into a hardcoded path. The "Ruthless" Demon is not impressed by your lies about linting. Fix your imports, fix your schema, and for the love of the Void, stop hardcoding paths!
