# Testing Report - Docgen V2

## 1. Scope
- **Repo:** ~/src/llmc
- **Feature:** Docgen V2 (Deterministic RAG-aware documentation generation)
- **Branch:** feature/docgen-v2
- **Date:** 2025-12-03
- **Agent:** Ren the Maiden Warrior Bug Hunting Demon

## 2. Summary
- **Overall Assessment:** **FLAWED**. While functional on the happy path, the implementation suffers from severe performance scalability issues and sloppy coding standards.
- **Key Risks:**
    - **Performance:** O(N * M) complexity where N=files and M=graph size. Loading the full graph for every file is catastrophic for large repos.
    - **Code Quality:** Numerous linting and typing errors indicate a rushed implementation.
    - **Resilience:** Shell backend error handling is permissive but relies on "skipping" rather than failing loud.

## 3. Environment & Setup
- **Commands:** `ruff check`, `mypy`, `pytest`
- **Environment:** Linux, Python 3.12
- **Status:** Setup successful, but required bypassing aggressive sleep blocking in tests.

## 4. Static Analysis
**Tool: `ruff check llmc/docgen`**
- **Issues:** 10
- **Severity:** Low to Medium
- **Key Findings:**
    - `PLW1510`: `subprocess.run` without explicit `check` argument (safety risk).
    - `UP024`: Deprecated `IOError` used instead of `OSError` (modernization failure).
    - `UP015`: Unnecessary `mode="r"` in `open()` calls (sloppy).
    - Import sorting violations (style).

**Tool: `mypy llmc/docgen`**
- **Issues:** 3
- **Severity:** Medium
- **Key Findings:**
    - `no-any-return`: Functions declared with strict return types return `Any` in `graph_context.py` and `config.py`. This defeats the purpose of type hints.

## 5. Test Suite Results
- **Unit Tests:** `tests/docgen` (33 passed), `tests/test_maasl_docgen.py` (18 passed).
- **New Ruthless Tests:**
    - `tests/test_docgen_ren.py`: **PASS** (Verified shell backend resilience).
    - `tests/test_locks_ren.py`: **PASS** (Verified locking, after fixing `pytest_ruthless` conflict).
    - `tests/test_docgen_perf_ren.py`: **FAILING CRITERIA** (Passed assertions but revealed high latency).

## 6. Behavioral & Edge Testing

**Operation: Graph Context Loading**
- **Scenario:** Large Repository (50k graph entities, batch processing)
- **Steps:** Run `build_graph_context` in a loop.
- **Observed:** ~91ms per call.
- **Impact:** For 1,000 files, this adds ~91 seconds of pure JSON parsing overhead. For 10,000 files, ~15 minutes.
- **Status:** **FAIL** (Performance)

**Operation: Shell Backend**
- **Scenario:** Malformed scripts, timeouts, garbage output.
- **Observed:** Correctly skips invalid results.
- **Status:** **PASS** (Resilience)

**Operation: Concurrency Locking**
- **Scenario:** Contention for lock file.
- **Observed:** Correctly waits and times out.
- **Note:** `open(..., 'w')` truncates the lock file repeatedly. While valid for `flock`, it's poor practice.

## 7. Documentation & DX Issues
- No documentation found explaining the `rag_graph.json` schema dependency.
- The `verify_docgen_phase1.py` script is trivial and validates types but not behavior.

## 8. Most Important Bugs (Prioritized)

1.  **Title:** O(N) Graph Loading Performance Catastrophe
    - **Severity:** **Critical** (Scaling block)
    - **Area:** Performance / Architecture
    - **Repro:** `pytest -s tests/test_docgen_perf_ren.py`
    - **Observed:** Full `rag_graph.json` (potentially MBs) is loaded from disk and parsed for *every single file* being documented.
    - **Expected:** Graph should be loaded once per batch or cached.

2.  **Title:** Missing `check=True` in Subprocess
    - **Severity:** High
    - **Area:** Safety
    - **File:** `llmc/docgen/backends/shell.py`
    - **Observed:** `subprocess.run` called without `check=True`. Exceptions are caught manually, but implicit failure checking is safer.

3.  **Title:** Broken Type Hints
    - **Severity:** Medium
    - **Area:** Code Quality
    - **File:** `llmc/docgen/graph_context.py`, `config.py`
    - **Observed:** Returning `Any` from typed functions.

## 9. Coverage & Limitations
- Assumed `rag_graph.json` exists and is valid for integration tests.
- Did not test Windows compatibility (locking relies on `fcntl`).
- Did not test actual `git` operations (mocked SHA).

## 10. Ren's Vicious Remark
"I've seen glaciers move faster than your graph loading logic. Loading the same JSON file 10,000 times? Did you think the disk needed exercise? Fix it before I start documenting your failures with a hammer."
