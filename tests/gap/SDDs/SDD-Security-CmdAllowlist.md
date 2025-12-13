# SDD: Command Allowlist Configuration Mismatch

## 1. Gap Description
The project configuration file `llmc.toml` defines `[mcp.tools] run_cmd_allowlist = [...]`. However, the configuration loader `llmc_mcp/config.py` reads `run_cmd_blacklist` from the TOML. Since `run_cmd_blacklist` is absent in the TOML, it defaults to an empty list.

The command execution tool `llmc_mcp/tools/cmd.py` uses this (empty) blacklist to validate commands. As a result, **all commands are allowed**, contrary to the explicit `allowlist` in the configuration. This is a critical security failure where the system fails open.

## 2. Target Location
`tests/gap/security/test_cmd_allowlist_config.py`

## 3. Test Strategy
1.  **Mock Config**: Load the `llmc.toml` file or a fixture that mimics it (containing `run_cmd_allowlist`).
2.  **Load Config**: Use `llmc_mcp.config.load_config` to parse it.
3.  **Assertion 1**: Check that `config.tools.run_cmd_blacklist` is empty (confirming the bug).
4.  **Assertion 2**: Check if `run_cmd_allowlist` is even processed or stored. It likely isn't.
5.  **Execution Test**: Initialize `LlmcMcpServer` with this config. Try to execute a command that is NOT in the allowlist (if the allowlist were working) but IS NOT in the blacklist (since it's empty).
    *   E.g., if allowlist has `['ls']`, try running `whoami`.
    *   Current behavior: `whoami` runs successfully (FAIL).
    *   Desired behavior: `whoami` is blocked.

## 4. Implementation Details
*   Use `llmc_mcp.config` and `llmc_mcp.tools.cmd`.
*   Create a temporary `llmc.toml` for the test if needed, or mock the file reading.
*   The test should confirm that `run_cmd_allowlist` from TOML has NO EFFECT on the loaded configuration's security constraints.
