# Testing Report - Ruthless Bug Hunt (Ren)

## 1. Scope
- **Repo:** ~/src/llmc
- **Branch:** feature/repo-onboarding-automation (dirty)
- **Commit:** 6f5d754 (latest)
- **Date:** 2025-12-04

## 2. Summary
- **Overall Assessment:** **CRITICAL ISSUES FOUND**. While recent security fixes (symlink, path traversal) are solid, the **test suite is rotting**. 
- **Key Risks:**
    - `pytest` suite is failing (10+ failures) due to type errors and stale assertions.
    - `tomlkit` dependency is required but not installed in the global environment (works in `.venv`).
    - `llmc/ruta` (User Testing Agent) code has potential runtime crashes (`None` attribute access).
    - Massive technical debt (700+ linting errors).

## 3. Environment & Setup
- **Setup:** `python3 -m llmc` works.
- **Failure:** `pytest` (without venv) failed to collect tests due to missing `tomlkit`.
- **Workaround:** Used `.venv/bin/pytest` and `.venv/bin/python` for all tests.

## 4. Static Analysis
- **Ruff:** 736 errors. 
    - High volume of `F841` (unused variables) and `F401` (unused imports).
    - Dangerous `B011` (assert False) and `PLW1510` (subprocess check).
- **Mypy:**
    - `llmc/ruta/judge.py:90`: `Item "None" ... has no attribute "get"`. **Runtime Crash Risk**.
    - `llmc/ruta/trace.py:68`: `Item "None" ... has no attribute "write"`. **Runtime Crash Risk**.
    - `tools/rag/inspector.py`: Multiple `None` vs `Path` type mismatches.

## 5. Test Suite Results
- **Command:** `.venv/bin/pytest tests/ --maxfail=10`
- **Status:** **FAIL** (Stopped after 10 failures)
- **Major Failures:**
    - `tests/test_e2e_daemon_operation.py`: **TypeError** `argument should be a str... not 'Mock'`. This is a Python 3.12 `pathlib` vs `Mock` incompatibility. The tests are broken.
    - `tests/test_e2e_operator_workflows.py`: **AssertionError** `Daemon service script should exist`. Checks for `scripts/llmc-rag-service` which was **DELETED** in this branch.
    - `tests/test_enrichment_config.py`: **Failed: DID NOT RAISE**. Confirms the "Routing Tier" feature works (validation relaxed), but the test is now wrong.

## 6. Behavioral & Edge Testing

### Operation: FTS5 Migration & Database Robustness
- **Scenario:** Missing DB tables, missing columns, invalid schema.
- **Status:** **PASS**
- **Notes:** Verified with `tests/ruthless/test_db_fts_ren.py`. Code handles schema errors by raising `RuntimeError` (safe crash).

### Operation: Docgen Lock Security (Symlink Attack)
- **Scenario:** Attacker links `.llmc/docgen.lock` to `target.txt`.
- **Status:** **PASS**
- **Notes:** Verified with `.trash/verify_lock_exploit.py`. Lock acquisition was refused, content was preserved.

### Operation: Ruthless Security Tests
- **Scenario:** Path traversal, graph injection.
- **Status:** **PASS**
- **Notes:** `tests/ruthless/*.py` passed (40 tests).

## 7. Documentation & DX Issues
- **Untracked Files:** `tests/ruthless/` is untracked. This valuable test collateral is at risk of being lost.
- **Stale Tests:** Tests asserting existence of deleted scripts causes confusion.

## 8. Most Important Bugs (Prioritized)

1.  **Title:** **Broken E2E Test Suite (Pathlib/Mock)**
    - **Severity:** **Critical** (CI is red)
    - **Area:** Tests
    - **Repro:** `.venv/bin/pytest tests/test_e2e_daemon_operation.py`
    - **Observed:** `TypeError: argument should be a str ... not 'Mock'`
    - **Expected:** Tests pass.
    - **Evidence:** Python 3.12 `pathlib.Path()` no longer accepts `Mock` objects gracefully if they don't mock `__fspath__`.

2.  **Title:** **Runtime Crash in RUTA Judge**
    - **Severity:** High
    - **Area:** `llmc/ruta/judge.py`
    - **Repro:** Static analysis (Mypy).
    - **Observed:** `incidents.get(...)` on potential `None`.
    - **Expected:** Null check before access.

3.  **Title:** **Stale Test: Removed Script Assertion**
    - **Severity:** Medium
    - **Area:** Tests
    - **Repro:** `.venv/bin/pytest tests/test_e2e_operator_workflows.py`
    - **Observed:** Asserts `scripts/llmc-rag-service` exists.
    - **Expected:** Test should check for new service entry point or be removed.

## 9. Ren's Vicious Remark
You fixed the security holes, I'll give you that. But your test suite is a burning dumpster fire. You deleted the scripts but left the tests looking for ghosts. And mocking Paths in 3.12 without `__fspath__`? Amateur hour. Clean up your room before you invite guests.
