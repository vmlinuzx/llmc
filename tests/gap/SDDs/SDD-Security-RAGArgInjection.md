# SDD: RAG Backend Argument Injection

## 1. Gap Description
The `llmc_agent/backends/llmc.py` file executes `rg` (ripgrep) and `llmc-cli` using `subprocess.run`. It passes the user-provided `query` directly as an argument without using the `--` delimiter. 

If a user provides a query starting with `-` (e.g., `-e pattern` or `--help`), the called tool may interpret it as a flag rather than a positional argument. This can lead to unexpected behavior, crashes, or potentially malicious flag injection (though `rg` and `llmc-cli` are relatively safe, it's a best practice violation and a functional bug).

## 2. Target Location
`tests/gap/security/test_rag_arg_injection.py`

## 3. Test Strategy
1.  **Mocking**: Mock `subprocess.run` to capture the arguments passed to it.
2.  **Scenario**: Instantiate `LLMCBackend` and call `search("-e --bad-flag")`.
3.  **Assertion**: Verify that `subprocess.run` was called. Check the argument list.
    *   **Fail Condition**: The argument list looks like `['rg', ..., '-e --bad-flag']`.
    *   **Pass Condition**: The argument list looks like `['rg', ..., '--', '-e --bad-flag']`. (Note: The test is expected to FAIL currently).
4.  **Integration (Optional)**: If mocking is too complex, we can run the actual code with a query like `--help` and check if it returns search results (it shouldn't) or help text (it shouldn't). But mocking is safer and faster.

## 4. Implementation Details
*   Create a test file that imports `LLMCBackend`.
*   Use `unittest.mock.patch` on `subprocess.run`.
*   The test should demonstrate that the current implementation fails to properly escape the query argument.
*   The test MUST fail on the current codebase.
