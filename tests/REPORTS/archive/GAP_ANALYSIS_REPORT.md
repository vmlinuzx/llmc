# Testing Report

## 1. Scope

- **Repo:** `llmc`
- **Subsystems:** Core `llmc`, `llmcwrapper`, `tools` (excluding `te` subsystem).
- **Date:** 2025-11-28
- **Agent:** Ren (Ruthless Testing Mode)

## 2. Summary

- **Overall Assessment:** **CRITICAL FAILURES**. The repository exhibits significant gaps in testing, critical bugs in production CLI entry points, and a massive amount of static analysis violations. The `llmcwrapper` package, which appears to be the user-facing layer, has zero unit coverage.
- **Key Risks:**
    - **Production Crashes:** The `rag-repo snapshot` command crashes 100% of the time due to a missing import.
    - **Unusable CLI:** The `llmc-rag` CLI does not accept user queries, failing with "unrecognized arguments".
    - **Blind Spots:** No tests for the Anthropic/Minimax providers or the main CLI logic.
    - **Maintenance Debt:** 965 linting errors suggest a codebase that is drifting from standards.
    - **Slow CI:** Test suite execution times out (>30s), hindering rapid feedback.

## 3. Environment & Setup

- **Python:** 3.11+ (implied by `ruff` config).
- **Dependencies:** `pytest` and `ruff` are configured.
- **Status:** Environment verified. `te` wrapper functions (though excluded from analysis).

## 4. Static Analysis

- **Tool:** `ruff check llmcwrapper tools`
- **Issues:** 965 errors found.
- **Critical Findings:**
    - `tools/rag_repo/cli_entry.py:35`: **Undefined name `SafeFS`**. This is a guaranteed runtime crash.
    - `tools/rag_nav/tool_handlers.py:314`: Unused variable `enriched_graph` (potential logic error).
    - `tools/rag_repo/utils.py`: Improper exception chaining (`B904`).

## 5. Test Suite Results

- **Inventory:** A large number of tests exist for `tools/rag` (search, graph, daemon), but...
- **Missing Coverage:**
    - **`llmcwrapper`**: 0 tests found. No `test_llmc_rag`, `test_anthropic`, `test_minimax`.
    - **`tools/rag_repo`**: Weak coverage. The `snapshot` command is clearly untested.
- **Performance:** Full test suite execution timed out (exit code 124) after 30s.
- **Reliability:** Cannot verify pass rate due to timeouts. `pytest --collect-only` passed.

## 6. Behavioral & Edge Testing

### Bug 1: `llmc-rag-repo snapshot` Crash
- **Operation:** `snapshot_workspace_cmd`
- **Scenario:** User attempts to create a snapshot of a workspace.
- **Steps to reproduce:** 
  ```python
  from tools.rag_repo.cli_entry import snapshot_workspace_cmd
  # ... call with valid paths ...
  ```
- **Expected behavior:** Returns a dictionary with snapshot path.
- **Actual behavior:** `NameError: name 'SafeFS' is not defined`.
- **Status:** **FAIL (CRITICAL)**
- **Evidence:** Reproduced via `tests/REPORTS/repro_safefs_crash.py`.

### Bug 2: `llmc-rag` CLI Usability
- **Operation:** `llmc-rag "query"`
- **Scenario:** User tries to run RAG with a query from CLI.
- **Steps to reproduce:** `python3 -m llmcwrapper.llmcwrapper.cli.llmc_rag "Why is the sky blue?"`
- **Expected behavior:** CLI accepts the query string.
- **Actual behavior:** `llmc_rag.py: error: unrecognized arguments: Why is the sky blue?`
- **Status:** **FAIL (High)**
- **Notes:** The CLI seems to hardcode a "ping" message and accepts no positional args.

## 7. Documentation & DX Issues

- **`llmc-rag`**: The name implies a RAG tool, but it behaves like a ping utility. This is confusing for users.
- **`llmc-yolo`**: Command exists but purpose is unclear from inspection (likely "do what I mean" mode).

## 8. Most Important Bugs (Prioritized)

1.  **Title:** `snapshot_workspace_cmd` crashes due to missing `SafeFS` import.
    -   **Severity:** Critical
    -   **Area:** `tools/rag_repo`
    -   **Fix:** Add `from .fs import SafeFS` to `tools/rag_repo/cli_entry.py`.

2.  **Title:** `llmc-rag` CLI rejects user input.
    -   **Severity:** High
    -   **Area:** `llmcwrapper`
    -   **Fix:** Add positional argument to `argparse` and pass it to `send()`.

3.  **Title:** Zero test coverage for `llmcwrapper`.
    -   **Severity:** High
    -   **Area:** Tests
    -   **Fix:** Create `tests/test_llmcwrapper_cli.py` and `tests/test_providers.py`.

## 9. Coverage & Limitations

- **Excluded:** `llmc/te` and `scripts/te` (as requested).
- **Timeouts:** Full suite run was incomplete due to timeouts.
