# SDD: Invalid RLM Configuration

## 1. Gap Description
The `McpConfig` and its nested `RLMConfig` are central to the new RLM feature. While happy-path configuration is likely tested, there is no evidence of testing for invalid or malformed configuration data. Supplying incorrect data types (e.g., a string for a boolean, a non-list for a list) could lead to uncaught exceptions or unpredictable behavior in the MCP server. This is an error-handling and robustness gap.

## 2. Target Location
`tests/mcp/test_rlm_config.py`

## 3. Test Strategy
The test strategy is to use `pytest.raises` to confirm that Pydantic's `ValidationError` is triggered when attempting to load an `McpConfig` with invalid data in the `rlm` section. We will test multiple fields with incorrect types and structures.

## 4. Implementation Details
- Create a new test function, e.g., `test_invalid_rlm_config_raises_validation_error`.
- Use a baseline valid configuration dictionary.
- In a parameterized test (`@pytest.mark.parametrize`), systematically introduce invalid values for the following `rlm` fields:
  - `enabled`: Pass a string `"true"`, an integer `1`, and `None`.
  - `provider`: Pass an integer `123`.
  - `models`: Pass a string `"model-name"` instead of a list of strings.
  - `tools`: Pass a dictionary `{"tool": "a"}` instead of a list of strings.
- For each case, use a `with pytest.raises(ValidationError):` block to wrap the `McpConfig(**config)` instantiation and assert that it fails as expected.
