# SDD: Missing Authentication Validation Tests

## 1. Gap Description
The `llmc_mcp` HTTP transport implements API key authentication via `APIKeyMiddleware`. However, the current test suite (`tests/test_mcp_http.py`) only verifies the "happy path" (successful authentication). There are no regression tests ensuring that:
1. Requests without an API key are rejected (401 Unauthorized).
2. Requests with an invalid API key are rejected (401 Unauthorized).
3. The `/health` endpoint remains public (200 OK without key).

This leaves the authentication mechanism vulnerable to accidental disablement or logic errors during refactoring.

## 2. Target Location
`tests/gap/test_auth_failure.py`

## 3. Test Strategy
The test should run against the live MCP daemon (detected on port 8765) or mock the server if the daemon is not running (though live testing is preferred given the current environment context).

**Test Cases:**
1. **Public Endpoint Check**: `GET /health` should return 200 OK without any auth headers.
2. **Missing Key Check**: `GET /tools/list` without `X-API-Key` header should return 401 Unauthorized.
3. **Invalid Key Check**: `GET /tools/list` with `X-API-Key: invalid-key-123` should return 401 Unauthorized.
4. **Valid Key Check**: `GET /tools/list` with the correct key (read from `~/.llmc/mcp-api-key`) should return 200 OK.

## 4. Implementation Details
- Use `pytest` and `httpx` (since `httpx` is already in the environment).
- Read the real API key from `Path.home() / ".llmc" / "mcp-api-key"`.
- If the key file is missing or the server is not reachable, the test should skip gracefully or fail with a clear message.
- Base URL: `http://localhost:8765`.
