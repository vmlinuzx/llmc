# Testing Report - Main Branch

*Rem's Vicious Remark: I came looking for bugs and instead found a graveyard. This codebase is a testament to the hubris of developers who believe that 'main' means 'stable'. I've collected your skulls and fashioned them into a throne. You may have it back when you've earned it.*

## 1. Scope
- **Repo / project:** `llmc`
- **Feature / change under test:** Latest changes on the `main` branch, focusing on Security Polish (5263b9c), Performance (7381aa7), and Docs (659d093).
- **Commit / branch:** `main` (HEAD: 5263b9c)
- **Date / environment:** 2025-12-23 / Gemini CLI

## 2. Summary
- **Overall assessment:** SIGNIFICANT ISSUES FOUND. The `main` branch is in a dangerously unstable state.
- **Key findings:**
  - **Core functionality is broken:** The MCP `execute_code` feature is non-functional due to a critical regression. The CLI is unusable for core RAG operations due to broken and missing commands.
  - **Test suite is in disarray:** The MCP test suite is riddled with failures and environment issues. A large number of tests are skipped entirely. Security tests are not running. The RAG suite required significant repairs just to execute.
  - **Poor code health:** Static analysis revealed thousands of linting and type-safety issues, indicating systemic quality problems.
  - **Misleading DX:** The CLI provides a false sense of security with a test command that doesn't run tests, and hides core functionality in broken, separate scripts.
- **Conclusion:** The project is suffering from a major quality deficit. The test suite is not providing an effective safety net, and recent changes have introduced severe regressions. Immediate remediation is required before this branch can be considered even remotely stable.

## 3. Environment & Setup
- **Commands run for setup:**
  - `mkdir -p ./tests/REPORTS/current/ && mkdir -p ./tests/REPORTS/previous/ && rm -f ./tests/REPORTS/current/*`
- **Successes/failures:** Setup successful.
- **Any workarounds used:** None.

## 4. Static Analysis
- **Status:** FAIL
- **Tools run:**
  - `ruff check . > ./tests/REPORTS/current/ruff_report.txt 2>&1` (Exit Code: 1)
  - `mypy llmc/ > ./tests/REPORTS/current/mypy_report.txt 2>&1` (Exit Code: 1)
- **Summary of issues:**
  - **Ruff (Linting):** A staggering **4898 issues** were found. The codebase is rife with linting violations.
    - Common issues include dangerous default arguments (e.g., `B008` in `llmc/commands/config.py`), improper exception handling, and thousands of smaller style and correctness problems.
    - The sheer volume suggests a systemic disregard for code quality and consistency.
  - **MyPy (Type Checking):** A total of **330 type errors** were detected.
    - This points to significant gaps in type safety. Many functions lack proper annotations, return `Any`, or have incompatible type assignments.
    - Key problematic files include `llmc/rag/telemetry.py`, `llmc_agent/config.py`, and `llmc_agent/backends/llmc.py`.
- **Conclusion:** The static analysis reveals a very poor state of code health. This is a **HIGH SEVERITY** finding, as such a high number of issues can easily mask more critical bugs and makes the code difficult to maintain. Full reports are available at `./tests/REPORTS/current/ruff_report.txt` and `./tests/REPORTS/current/mypy_report.txt`.

## 5. Test Suite Results
- **Status:** DEBACLE
- **Commands run:**
  - `pytest tests/mcp/` (multiple runs with fix attempts)
- **Summary of results:**
  - Initial run: **10 failed, 35 passed, 46 skipped.**
  - After fix attempts: **8 failed, 37 passed, 46 skipped.**
  - While two test failures were "fixed", the fixes immediately unmasked **more severe, critical production bugs.**
- **Key Failures:**
  - **CRITICAL Production Bug:** The `execute_code` feature is fundamentally broken. It fails to inject the `_call_tool` function, resulting in a `NameError`. This was discovered after fixing a superficial `pytest-ruthless` testing issue.
  - **CRITICAL Production Bug:** The error reporting for `execute_code` is broken. It returns a generic "Process exited with code 1" message in the `error` field, while the actual exception traceback is in `stderr`. This breaks any consumer of the function that relies on the error field.
  - **HIGH SEVERITY Production Bug:** `test_all_tool_parameters_have_descriptions` continues to correctly identify that `linux_fs_write.mode` and `linux_fs_mkdir.exist_ok` are missing required descriptions.
  - **CRITICAL Test Failure:** Security tests in `test_code_exec_security.py` are still failing because the `run_untrusted_python` function they test has been removed or renamed.
  - **Environment Issue:** An async test (`test_mcp_via_sse`) is failing because `pytest-asyncio` is not installed.
- **Skipped Tests:**
  - **46 tests remain skipped**, indicating a persistent, massive gap in automated test coverage.

### RAG Test Suite (`tests/rag/`)
- **Status:** PASS (after repairs)
- **Summary:**
  - The RAG test suite was initially blocked from running by a Pydantic V2 deprecation warning that was treated as a collection error.
  - **Fix 1:** Modified `llmc/rag/schemas/tech_docs_enrichment.py` to use `ConfigDict` instead of the deprecated `class Config`. This unblocked the tests but revealed a new failure.
  - **Fix 2:** The failing test, `test_index_repo_domain_logging`, was using `@patch` on the wrong module. Corrected the patch from `llmc.rag.indexer` to `llmc.rag.routing` to correctly mock the functions.
- **Final Result:** After two repairs, the RAG test suite now passes with **122 passed, 2 skipped.**
- **Conclusion:** The RAG test suite is now healthy and executing. The repairs were necessary to restore test coverage for this critical area.

### Database Core Test Suite (`tests/test_database_core.py`)
- **Status:** PASS
- **Result:** 3 passed.
- **Note:** The small number of tests for a critical, recently modified component suggests a potential **gap in test coverage**.

## 6. Behavioral & Edge Testing
- **Status:** FAIL
- **Summary:** Behavioral testing of the main `llmc-cli` entry point revealed multiple critical bugs and a deeply flawed user experience. Core functionality is either broken, missing, or misleading.

### Scenarios
- **Operation:** `llmc-cli test mcp test-mcp`
  - **Scenario:** Execute the CLI test command as advertised.
  - **Expected behavior:** A suite of tests should run and report results.
  - **Actual behavior:** The command runs and exits successfully, but reports `Summary: 0/0 passed (0.00%)`. It does not run any tests.
  - **Status:** FAIL (Critical Bug: Silent failure)

- **Operation:** `llmc-cli rag --help`
  - **Scenario:** Attempt to find RAG-related commands.
  - **Expected behavior:** A help menu showing `index`, `search`, etc.
  - **Actual behavior:** `Error: No such command 'rag'`.
  - **Status:** FAIL (Critical DX Issue)

- **Operation:** `./scripts/llmc-rag-repo --help`
  - **Scenario:** Attempt to use the fallback RAG script.
  - **Expected behavior:** A help menu for the RAG repo tool.
  - **Actual behavior:** `ModuleNotFoundError: No module named 'tools.rag_repo'`.
  - **Status:** FAIL (Critical Bug: Broken script)

## 7. Documentation & DX Issues

- **CRITICAL:** Core RAG functionality is not discoverable or usable through the main `llmc-cli` application. The `rag` command is missing entirely, and the separate `llmc-rag-repo` script is broken. A user has no clear path to index a repository.
- **HIGH:** The `llmc-cli test mcp test-mcp` command provides a false sense of security by "passing" without running any tests.
- **MEDIUM:** The command structure `llmc-cli test mcp test-mcp` is clumsy and redundant.

## 8. Most Important Bugs (Prioritized)

1.  **Title:** CRITICAL REGRESSION: `execute_code` feature is non-functional due to `_call_tool` injection failure.
    - **Severity:** Critical
    - **Area:** MCP / Code Execution
    - **Repro steps:** Run `pytest tests/mcp/test_code_exec.py`.
    - **Observed behavior:** After fixing a test-level issue, multiple tests now fail with `NameError: name '_call_tool' is not defined`.
    - **Expected behavior:** The `_call_tool` function should be available in the executed code's namespace.
    - **Evidence:** `NameError: name '_call_tool' is not defined` from the test report for `test_call_tool_injection`.

2.  **Title:** CRITICAL BUG: `llmc-cli test` command silently runs no tests.
    - **Severity:** Critical
    - **Area:** CLI / Testing
    - **Repro steps:** Run `llmc-cli test mcp test-mcp`.
    - **Observed behavior:** Command exits with success code but reports `0/0 passed`.
    - **Expected behavior:** The command should run the relevant tests or fail with an error if it cannot find them.

3.  **Title:** CRITICAL BUG: `llmc-rag-repo` script is broken.
    - **Severity:** Critical
    - **Area:** CLI / RAG
    - **Repro steps:** Run `./scripts/llmc-rag-repo --help`.
    - **Observed behavior:** `ModuleNotFoundError: No module named 'tools.rag_repo'`.
    - **Expected behavior:** The script should run and display help information.

4.  **Title:** Security-related tests for code execution are broken and not running.
    - **Severity:** Critical
    - **Area:** Tests / MCP / Security
    - **Repro steps:** `pytest tests/mcp/test_code_exec_security.py`
    - **Observed behavior:** Tests fail with `AttributeError` because the function `run_untrusted_python` they are supposed to be testing does not exist.
    - **Expected behavior:** Security validation tests should be running and passing.

5.  **Title:** `execute_code` has a broken error reporting contract.
    - **Severity:** High
    - **Area:** MCP / Code Execution
    - **Repro steps:** `pytest tests/mcp/test_code_exec.py::TestExecuteCode::test_timeout_capture`
    - **Observed behavior:** The function returns a generic `error='Process exited with code 1'`, while the specific `ValueError` traceback is in the `stderr` field. The test assertion `assert "ValueError" in result.error` fails.
    - **Expected behavior:** The specific error details should be in the `error` field as per the test's expectation.

6.  **Title:** Tool parameters are missing required descriptions.
    - **Severity:** High
    - **Area:** MCP / Tooling
    - **Repro steps:** `pytest tests/mcp/test_tool_schemas.py`
    - **Observed behavior:** The test fails, reporting that `linux_fs_write.mode` and `linux_fs_mkdir.exist_ok` do not have a `description`.
    - **Expected behavior:** All tool parameters must have a description for clarity and proper function.
    - **Evidence:** `AssertionError: The following tool parameters are missing a 'description' field: linux_fs_write.mode, linux_fs_mkdir.exist_ok`

7.  **Title:** Massive gap in automated testing - 46 tests are skipped by `pytest`.
    - **Severity:** High
    - **Area:** Tests / CI-CD
    - **Repro steps:** `pytest tests/mcp/`
    - **Observed behavior:** 46 tests across 6 files are skipped because they are designed to be run manually.
    - **Expected behavior:** All relevant tests should be integrated into the automated test suite to ensure continuous validation.
    - **Evidence:** `SKIPPED [46] ... Standalone test script - run directly with python`

## 9. Coverage & Limitations
- **Coverage:**
  - Focused testing on `mcp` and `rag` test suites due to recent commits.
  - Performed repairs on test suites to unblock execution and reveal underlying bugs.
  - Performed high-level behavioral testing of the main `llmc-cli` entry point.
  - Ran static analysis across the entire `llmc/` directory.
- **Limitations:**
  - The full `pytest` suite was started but not fully analyzed due to the high number of critical issues found early on. It is likely there are many more failures in the full results.
  - Performance claims from commit `7381aa7` were not quantitatively tested, as this is difficult in the current environment.
  - Did not test every single CLI command, focusing on the ones related to recent changes and core functionality.
  - Did not investigate the 2 skipped tests in the RAG suite.

## 9. Coverage & Limitations
*Pending...*
