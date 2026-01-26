# SDD: RLM Tool Backend Failure

## 1. Gap Description
The `RLMTool` in `llmc_mcp/tools/rlm.py` is responsible for communicating with a backend RLM provider. There are no tests to verify the tool's behavior when this backend communication fails. Scenarios like network connection errors, request timeouts, non-200 HTTP status codes, or malformed JSON responses from the backend are not covered. This can lead to unhandled exceptions and server instability.

## 2. Target Location
`tests/mcp/test_tool_rlm.py`

## 3. Test Strategy
The strategy is to mock the HTTP client used by the `RLMTool` (e.g., `httpx.AsyncClient`). The mock will be configured to simulate various failure modes. We will then call the tool's execution method and assert that it catches the exceptions and returns a structured, user-friendly error message.

## 4. Implementation Details
- Add `pytest-mock` to the testing dependencies if not already present.
- Create a new test function, e.g., `test_rlm_tool_backend_failures`.
- Use the `mocker` fixture to patch the HTTP client within the `llmc_mcp.tools.rlm` module.
- Create parameterized tests (`@pytest.mark.parametrize`) for the following failure scenarios:
  - **Connection Error:** The mock's `post` method should raise `httpx.ConnectError`.
  - **Timeout:** The mock's `post` method should raise `httpx.Timeout`.
  - **Server Error:** The mock's response object should have a status code of 500.
  - **Invalid JSON:** The mock's response object should have a 200 status code but contain invalid JSON text.
- In each test case, execute the `RLMTool.run()` method.
- Assert that the tool does not raise an unhandled exception.
- Assert that the returned result is an error message (e.g., a dictionary `{"error": "...", "status_code": ...}`).
