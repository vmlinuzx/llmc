# SDD: MCP Command Validation Gaps

## 1. Gap Description
The `validate_command` function in `llmc_mcp/tools/cmd.py` implements a blacklist-based security control. This approach is known to be fragile. Specifically, it only checks the binary name (first token) against the blacklist. It does not inspect arguments, allowing trivial bypasses (e.g., using a non-blacklisted interpreter to run a blacklisted command).

## 2. Target Location
`tests/gap/test_mcp_cmd_validation.py`

## 3. Test Strategy
We will write a test suite that characterizes the current behavior, explicitly verifying that the blacklist CAN be bypassed. This documents the security gap.

1.  **Direct Block**: Verify that `node` is blocked if `node` is in blacklist.
2.  **Path Resolution**: Verify that `/usr/bin/node` is blocked if `node` is in blacklist (this should work correctly per code).
3.  **Argument Bypass (The Gap)**: Verify that `bash -c "node script.js"` is ALLOWED even if `node` is in blacklist (assuming `bash` is not).

## 4. Implementation Details
- Import `validate_command`, `CommandSecurityError` from `llmc_mcp.tools.cmd`.
- **Test Case 1**: `validate_command(["node", "script.js"], blacklist=["node"])` -> Raises `CommandSecurityError`.
- **Test Case 2**: `validate_command(["/usr/bin/node", "script.js"], blacklist=["node"])` -> Raises `CommandSecurityError`.
- **Test Case 3 (The Bypass)**: `validate_command(["bash", "-c", "node script.js"], blacklist=["node"])` -> Returns "bash" (Does NOT raise error).
