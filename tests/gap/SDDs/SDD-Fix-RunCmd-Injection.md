# SDD: Fix Command Injection in `run_cmd`

## 1. Gap Description
The `run_cmd` tool in `llmc_mcp/tools/cmd.py` is vulnerable to command injection. It uses `subprocess.run(..., shell=True)` while only validating the first token of the command string against a blacklist. This allows attackers to bypass the blacklist by chaining commands (e.g., `echo hello; malicious_cmd`).

## 2. Target Location
- Implementation: `llmc_mcp/tools/cmd.py`
- Test: `tests/mcp/test_cmd_security.py`

## 3. Test Strategy
1.  **Regression Test**: Create a test case that attempts to execute a chained command (e.g., `echo 'safe'; echo 'VULN'`).
2.  **Assertion**: Verify that the second command is *not* executed as a separate shell command. With `shell=False`, `echo 'safe'; echo 'VULN'` should either fail (if `echo` doesn't accept `;` as arg) or print the literal string including the semicolon. It should NOT execute the second echo.
3.  **Positive Test**: Verify that standard commands still work (e.g., `ls -la`).
4.  **Isolation**: Ensure tests run with `LLMC_ISOLATED=1` to bypass the isolation check during testing.

## 4. Implementation Details
1.  **Modify `run_cmd`**:
    -   Remove `shell=True`.
    -   Pass the *list* of command parts (from `shlex.split`) to `subprocess.run`.
    -   Update `validate_command` if necessary (though it returns the binary name, we need the full list for `subprocess.run`).
2.  **Handle Fallback**: If `shell=False` breaks too many valid use cases (like pipes), we might need a fallback or explicit "shell mode" that is strictly isolated. For now, **enforce `shell=False`** as the primary fix.
3.  **Environment**: Ensure `subprocess.run` receives `env=env` and `cwd=...`.

**Note**: This change effectively disables shell features like `|`, `>`, `&&` in `run_cmd`. This is a necessary security hardening. Users needing pipelines should use `te_run` or composed tools.
