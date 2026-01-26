# SDD: P1-MCP-RLM-Tool-Integration-Tests

## 1. Gap Description
**Severity:** P1 (High)

The `mcp_rlm_query` function in `llmc_mcp/tools/rlm.py` implements numerous critical security policies and error handling paths (e.g., feature flags, argument validation, model egress controls, path denylists, file size limits, timeouts). However, these code paths are not covered by any dedicated integration tests. This creates a high risk of regressions and makes it impossible to verify that the security controls are functioning as designed. The original roadmap for this feature explicitly called for the creation of `tests/mcp/test_tool_rlm.py`.

## 2. Target Location
- **Test File:** `tests/mcp/test_tool_rlm.py` (to be created or augmented)
- **File Under Test:** `llmc_mcp/tools/rlm.py`

## 3. Test Strategy
The test suite will use `pytest` and `pytest-asyncio`. The core strategy involves isolating the `mcp_rlm_query` function and testing its logic against various configurations and inputs.

- **Mocking:** The `llmc.rlm.session.RLMSession` will be mocked using `unittest.mock.AsyncMock` to prevent actual LLM calls and to simulate different outcomes (success, failure, exceptions).
- **Configuration:** Test fixtures will provide instances of `McpRlmConfig` representing different security postures (e.g., "unrestricted" vs. "restricted").
- **Filesystem:** `pyfakefs` will be used to create a virtual filesystem for testing path-based operations, including file-not-found, permission errors, and size limit checks.

## 4. Implementation Details

A new test file `tests/mcp/test_tool_rlm.py` should be created with the following test cases (or similar):

### Test Fixtures
-   `mocker`: The standard pytest-mock fixture.
-   `fs`: The `pyfakefs` fixture.
-   `default_config`: A fixture that returns a default, permissive `McpRlmConfig`.
-   `restricted_config`: A fixture that returns a locked-down, `profile="restricted"` `McpRlmConfig`.
-   `mock_rlm_session`: A fixture that patches `llmc_mcp.tools.rlm.RLMSession` with an `AsyncMock`.

### Test Cases
-   **Happy Path:**
    -   `test_success_with_path_context`: Test a successful query using a file path.
    -   `test_success_with_string_context`: Test a successful query using a raw string context.
-   **Argument Validation:**
    -   `test_error_on_missing_task`: Verify it fails when `task` is empty.
    -   `test_error_on_long_task`: Verify it fails when `task` is too long.
    -   `test_error_on_both_path_and_context`: Verify it fails when both `path` and `context` are provided.
    -   `test_error_on_neither_path_nor_context`: Verify it fails when neither is provided.
-   **Security Policy Enforcement:**
    -   `test_rlm_disabled`: Test that the tool returns a "disabled" error when `config.enabled=False`.
    -   `test_model_override_denied`: Test that using the `model` argument fails when `allow_model_override=False`.
    -   `test_restricted_profile_denies_unlisted_model`: Test that the restricted profile blocks models not in the `allowed_model_prefixes`.
    -   `test_path_query_denied`: Test that using the `path` argument fails when `allow_path=False`.
    -   `test_denylist_glob_prevents_access`: Test that a file matching a `denylist_globs` pattern is blocked.
-   **Error Handling:**
    -   `test_file_not_found`: Use `pyfakefs` to test the response for a non-existent file.
    -   `test_permission_error`: Use `pyfakefs` to test the response for a file with no read permissions.
    -   `test_file_too_large`: Test the error response when a file's size exceeds `max_bytes`.
    -   `test_timeout_error`: Configure the mock `RLMSession` to raise `asyncio.TimeoutError` and verify the correct error is returned.
-   **Resource Management:**
    -   `test_file_read_is_truncated`: Verify that `read_text` is only called up to `max_bytes`. This can be a separate SDD, but a basic test is good.
