# Gap Analysis Report: MCP Security & Coverage

**Date**: 2025-12-07
**Agent**: Rem (Gap Analysis Demon)

## Summary
A comprehensive gap analysis of the `llmc_mcp` module revealed a critical security vulnerability in `run_cmd` and missing test coverage for protected filesystem operations and isolation checks. All identified gaps have been addressed.

## Findings & Actions

### 1. Critical Security Vulnerability: Command Injection in `run_cmd`
-   **Gap**: The `run_cmd` tool used `subprocess.run(..., shell=True)` but relied on a weak blacklist validation that only checked the first token. This allowed attackers to bypass the blacklist using chained commands (e.g., `echo hello; malicious_cmd`).
-   **Action**: 
    -   Modified `llmc_mcp/tools/cmd.py` to use `shell=False`.
    -   Updated the execution logic to pass the parsed command list (from `shlex.split`) directly to `subprocess`.
    -   Added regression tests in `tests/mcp/test_cmd_security.py` verifying that chained commands are treated as literal arguments, preventing execution of the second command.
-   **Status**: ✅ **FIXED**

### 2. Missing Coverage: `fs_protected` Logic
-   **Gap**: The `llmc_mcp/tools/fs_protected.py` module, which handles critical file locking via MAASL, had zero unit test coverage.
-   **Action**:
    -   Created `tests/mcp/test_fs_protected.py`.
    -   Implemented tests for `write_file_protected`, `move_file_protected`, `delete_file_protected`.
    -   Verified locking mechanics (mocking MAASL) and error handling.
    -   **Bug Fix**: Identified and fixed a bug in `fs_protected.py` where `ResourceBusyError.message` (non-existent attribute) was accessed.
-   **Status**: ✅ **COVERED**

### 3. Missing Coverage: `run_cmd` Isolation Enforcement
-   **Gap**: The `require_isolation` check in `run_cmd` lacked tests ensuring it actually blocks execution in non-isolated environments.
-   **Action**:
    -   Created `tests/mcp/test_cmd_isolation.py`.
    -   Added tests verifying failure on bare metal and success with `LLMC_ISOLATED=1` or container markers.
-   **Status**: ✅ **COVERED**

## Conclusion
The `llmc_mcp` module's security posture has been significantly improved. The critical command injection vector is closed, and the robustness of file operations and environment checks is now verified by automated tests.
