# SDD: P1-RLM-Session-Tests

## 1. Gap Description
**Severity:** P1 (High)

The `RLMSession` class in `llmc/rlm/session.py` is the core engine of the RLM feature, orchestrating budget management, sandboxed code execution, AST-based tool call interception, and the main conversational loop with the LLM. This class is highly complex and stateful, yet it lacks any dedicated unit or integration tests. This absence of testing makes it impossible to guarantee the correctness of its critical functions (especially budget enforcement and security sandboxing) and exposes the project to a high risk of regressions.

## 2. Target Location
- **Test File:** `tests/rlm/test_session.py` (to be created)
- **File Under Test:** `llmc/rlm/session.py`

## 3. Test Strategy
A new test suite will be created using `pytest` and `pytest-asyncio` to thoroughly test the `RLMSession`'s lifecycle and logic.

- **Mocking Strategy:**
    -   `litellm.acompletion` and `litellm.completion` will be mocked with `unittest.mock.AsyncMock` to simulate LLM responses without network calls. This allows for testing the turn-based loop, prompt construction, and response parsing.
    -   `llmc.rlm.sandbox.interface.create_sandbox` will be patched to return a mock sandbox object. This will allow tests to control the outcome of code execution (`ExecutionResult`) and verify that the correct code is being passed to the sandbox.
    -   `llmc.rlm.nav.treesitter_nav.TreeSitterNav` will be mocked to isolate session logic from the navigation component.
- **Configuration:** A test fixture will provide a default `RLMConfig` instance that can be customized for specific tests (e.g., to test low budget limits).

## 4. Implementation Details

The new test file `tests/rlm/test_session.py` should include the following tests:

### Test Fixtures
-   `mock_litellm`: A fixture that patches `litellm.acompletion` and `litellm.completion`.
-   `mock_sandbox`: A fixture that patches `create_sandbox` and returns a configurable mock.
-   `default_rlm_config`: A fixture for a standard `RLMConfig`.

### Test Cases
-   **Initialization and Context Loading:**
    -   `test_initialization`: Verify that the session initializes its components (budget, sandbox) correctly.
    -   `test_load_code_context_file_too_large`: Test that `load_code_context` raises a `ValueError` for a file exceeding the configured size limit. Use `pyfakefs`.
-   **Main `run` Loop Logic:**
    -   `test_run_success_single_turn`: Test a simple case where the LLM returns a `FINAL(answer)` in the first turn.
    -   `test_run_loop_with_code_execution`: Test a multi-turn scenario where the LLM returns code, the sandbox executes it, and the results are fed back into the next turn's prompt.
    -   `test_run_respects_max_turns`: Verify that the loop terminates after `max_turns` is reached.
    -   `test_run_handles_session_timeout`: Configure the mock budget to simulate an elapsed time greater than the timeout and assert that the session stops.
-   **Budget Enforcement:**
    -   `test_run_stops_on_root_call_budget_exceeded`: Configure the mock `budget.check_and_reserve` to raise `BudgetExceededError` on a root call and verify the session terminates gracefully.
    -   `test_llm_query_tool_stops_on_sub_call_budget_exceeded`: Test the internal `llm_query` tool and ensure it returns an error message when its budget is exceeded.
-   **Tool Call Interception (Phase 1):**
    -   `test_ast_interception_rewrites_code`: Provide code with a whitelisted `nav_*` call and verify that the code passed to the sandbox is the rewritten version.
    -   `test_ast_interception_handles_tool_error`: Simulate an exception during the execution of an intercepted tool and ensure the error is handled correctly.
-   **Error Handling:**
    -   `test_run_handles_root_model_error`: Configure the mock `litellm.acompletion` to raise an exception and verify the session returns a failed `RLMResult`.
