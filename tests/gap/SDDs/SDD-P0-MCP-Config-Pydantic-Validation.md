# SDD: P0-MCP-Config-Pydantic-Validation

## 1. Gap Description
**Severity:** P0 (Critical)

The `llmc_mcp/config.py` module uses standard Python `dataclasses` and manual `.validate()` methods for configuration. This approach is brittle, error-prone, and lacks the robust, automatic validation and clear error reporting for nested structures that Pydantic provides. A pre-existing failing test, `test_invalid_rlm_config_raises_validation_error`, was designed to expose this specific weakness. The current implementation cannot provide the detailed validation error messages that Pydantic excels at.

## 2. Target Location
- **Primary:** `llmc_mcp/config.py`
- **Driving Test:** `tests/mcp/test_rlm_config.py`

## 3. Test Strategy
The implementation will be considered complete when the test `test_invalid_rlm_config_raises_validation_error` in `tests/mcp/test_rlm_config.py` passes. The strategy is to refactor the configuration loading to leverage Pydantic, which will naturally satisfy the test's assertions for structured validation errors.

## 4. Implementation Details
The core of this task is to replace the `dataclasses` with Pydantic `BaseModel`.

1.  **Add Dependency:** Add `pydantic` to the `[project.dependencies]` in `pyproject.toml`.
2.  **Refactor Dataclasses to Pydantic Models:**
    - In `llmc_mcp/config.py`, change all `@dataclass` decorated classes to inherit from `pydantic.BaseModel`.
    - Convert `field(default_factory=...)` to Pydantic's `Field(default_factory=...)`.
3.  **Replace Manual Validation:**
    - Remove all custom `.validate()` methods.
    - Replace them with Pydantic validators (`@field_validator` for newer Pydantic versions) or by using constrained types (e.g., `max_request_bytes: int = Field(gt=0)`). For string choices like `profile: str = "unrestricted"`, use `Literal["restricted", "unrestricted"]`.
4.  **Update `load_config` function:**
    - Remove the manual, field-by-field parsing from the TOML data.
    - Instead, after loading the TOML dictionary, use `McpConfig.model_validate(mcp_data)` to parse and validate the entire structure at once.
    - The `_apply_env_overrides` function will need to be adjusted to work with the Pydantic model, possibly by updating the model instance directly before a final validation pass.
