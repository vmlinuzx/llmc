# AAR: Gap Analysis - Authentication & Security

## Mission Summary
**Date**: 2025-12-13
**Agent**: Rem (Gap Analysis Demon)
**Scope**: `llmc_mcp` (Server, Transport, Tools)

## Gaps Identified

### 1. Missing Authentication Validation (Severity: HIGH)
- **Description**: The HTTP transport implements `APIKeyMiddleware`, but no tests verified that requests *without* keys or with *invalid* keys were rejected.
- **Action**: Created `tests/gap/SDDs/SDD-Auth-Validation.md` and spawned a worker to implement `tests/gap/test_auth_failure.py`.
- **Result**:
    - **Initial Failure**: The test failed on the "valid key" case because it targeted a non-existent `/tools/list` endpoint.
    - **Fix**: Updated the test to use the `/sse` endpoint (which is the actual protected endpoint exposed by `http_server.py`).
    - **Success**: The updated test passed (4/4 cases), confirming that `APIKeyMiddleware` correctly returns `401 Unauthorized` for missing/invalid keys and `200 OK` for valid keys.
    - **Discovery**: The test revealed that the `/tools/list` endpoint (referenced in legacy `test_mcp_http.py`) **does not exist** in the current `http_server.py`. The server only supports SSE transport.
    - **Implication**: The existing `test_mcp_http.py` is obsolete and broken.

### 2. Insecure Command Execution (Severity: CRITICAL)
- **Description**: The `run_cmd` tool relies on a `run_cmd_blacklist` configuration.
- **Vulnerability**: 
    - Blacklisting is an ineffective security control for shell commands.
    - If `sh` or `bash` are not blacklisted (default blacklist is empty), arbitrary code can be executed via `sh -c "..."`.
    - `LLMC_ISOLATED=1` environment variable allows bypassing the isolation check, enabling arbitrary host code execution via `run_cmd` or `execute_code`.

### 3. Code Execution Sandbox Default (Severity: HIGH)
- **Description**: `McpCodeExecutionConfig` defaults to `sandbox = "subprocess"`.
- **Vulnerability**: "Subprocess" sandbox is not a sandbox; it runs on the host (unless the server itself is containerized). This is a dangerous default for a CLI application.

## Artifacts Created
- `tests/gap/SDDs/SDD-Auth-Validation.md`
- `tests/gap/test_auth_failure.py`

## Recommendations
1. **Refactor Auth Tests**: Update `tests/gap/test_auth_failure.py` to use `/sse` instead of `/tools/list`.
2. **Deprecate Legacy Test**: Delete or update `tests/test_mcp_http.py`.
3. **Harden `run_cmd`**: Replace blacklist with a strict whitelist or remove `run_cmd` entirely in favor of specific tools.
4. **Enforce Isolation**: Require `docker` or `nsjail` for code execution; remove `subprocess` option or mark it as `INSECURE_DEV_ONLY`.
