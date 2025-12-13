# SDD: MCP Command Policy & Isolation

## 1. Gap Description
The `run_cmd` tool in `llmc_mcp` has security features (Isolation Requirement, Binary Blacklist), but they are not fully covered by existing tests.
- **Isolation Gap**: Existing tests (`tests/mcp/test_cmd_security.py`) forcefully enable isolation (`LLMC_ISOLATED=1`). There is no test ensuring that `run_cmd` *fails* safely when isolation is missing (bare metal protection).
- **Blacklist Gap**: The blacklist logic exists but is not tested. Existing tests check for command injection syntax, not policy enforcement. We need to verify that adding a binary to the blacklist actually blocks it.

## 2. Target Location
`tests/gap/test_mcp_cmd_policy.py`

## 3. Test Strategy
1.  **Isolation Test**:
    -   Unset `LLMC_ISOLATED` and ensure no other isolation markers (dockerenv etc.) are present (mocking `is_isolated_environment` or environment vars).
    -   Call `run_cmd`.
    -   Assert `success=False` and error message contains "requires an isolated environment".
2.  **Blacklist Test**:
    -   Set `LLMC_ISOLATED=1` (to pass the first check).
    -   Call `run_cmd` with a custom blacklist containing `ls`.
    -   Command: `ls -la`.
    -   Assert `success=False` and error message contains "blacklisted".
    -   Call `run_cmd` with a non-blacklisted command (`echo`).
    -   Assert `success=True`.

## 4. Implementation Details
-   Use `pytest` and `unittest.mock.patch.dict` for environment manipulation.
-   Import `run_cmd` from `llmc_mcp.tools.cmd`.
-   Ensure tests do not depend on actual external tools for the "failure" cases (mocking or using simple tools like `ls`).
