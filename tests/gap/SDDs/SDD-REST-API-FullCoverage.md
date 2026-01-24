# SDD: REST API v1 Full Test Coverage

## 1. Gap Description

The REST API v1 was implemented and merged without any corresponding integration or unit tests. This leaves the entire API surface area, including authentication, rate limiting, and core business logic, unvalidated and prone to breakage. This SDD outlines the comprehensive test suite required to achieve full coverage.

## 2. Target Location

A **new test file** shall be created at: `tests/transport/test_rest_api.py`.

This new file will contain all tests described below. The existing `tests/test_mcp_http_transport.py` must NOT be modified.

## 3. Test Strategy

The testing strategy will use a combination of `pytest` and Starlette's `TestClient`.

- **TestClient:** A `TestClient` instance will be created, wrapping the full Starlette application with the REST API mounted. This enables end-to-end integration tests without a live server.
- **Fixtures:** Pytest fixtures will be used to manage test setup, such as creating a temporary workspace, building a mock RAG index, and configuring the application for different authentication modes.
- **Mocking:** `unittest.mock` will be used to patch the underlying RAG functions (`search_spans`, etc.) to isolate endpoint logic and test different data return scenarios without needing a real, complex index. The `run_in_threadpool` calls must be mocked to run synchronously in the test environment.

## 4. Implementation Details

### 4.1. Test Setup (Fixtures)

A `conftest.py` or the test file itself should define the following fixtures:

- **`mock_rag_index_path`**: Creates a temporary directory with a dummy `.rag` subdirectory to simulate an indexed workspace.
- **`test_config`**: Creates an `llmc.toml` configuration dynamically, allowing tests to override `[mcp.rest_api]` and `[mcp.workspaces]` sections.
- **`client_factory`**: A factory fixture that takes config settings and returns a configured `TestClient` instance. This will allow creating clients for different auth modes (`"auto"`, `"token"`, `"none"`).
- **`mock_api_key`**: Provides a static API key for testing token-based auth.

### 4.2. Authentication & Middleware Tests

This is the most critical area to test first.

- **`RestAuthMiddleware` Tests:**
  - **Auth Mode `auto`**:
    - Request from `127.0.0.1` (the `TestClient` default) to a protected endpoint **succeeds** without an API key.
    - Request with `X-Forwarded-For: 8.8.8.8` (and `trust_proxy=true`) to a protected endpoint **fails (401)** without an API key.
    - Request with `X-Forwarded-For: 8.8.8.8` (and `trust_proxy=true`) to a protected endpoint **succeeds** with a valid API key.
  - **Auth Mode `token`**:
    - Request from `127.0.0.1` **fails (401)** without an API key.
    - Request from `127.0.0.1` **succeeds** with a valid API key.
    - Request from `127.0.0.1` **fails (401)** with an invalid API key.
  - **Auth Mode `none`**:
    - Request from a remote IP (simulated via header) **succeeds** without an API key.
- **Health Endpoint Exception**:
  - Verify `GET /api/v1/health` is **always** public and returns 200, regardless of auth mode or client IP.
- **Rate Limiting Middleware Tests**:
  - Configure a low rate limit (e.g., 5 RPM).
  - Make 5 requests; all should succeed.
  - Make the 6th request; it should **fail (429)** with the correct error code.
  - Check for `X-RateLimit-` headers on responses.

### 4.3. Endpoint Tests

For each endpoint, test the following scenarios:

#### `GET /api/v1/health`
- **Happy Path**: Returns 200 OK.
- **Content**: Response body contains `"status": "ok"` and a list of configured workspaces.

#### `GET /api/v1/workspaces`
- **Happy Path**: Returns 200 OK.
- **Content**: Response body lists the workspaces defined in the test config, including their `id`, `path`, and `indexed` status.

#### `GET /api/v1/workspaces/{id}/search`
- **Happy Path**: Returns 200 OK with a valid `q` parameter.
- **Mocked Backend**: Mock `run_in_threadpool` to return a canned list of search results and verify they are present in the response body.
- **Missing Query**: Request without a `q` parameter fails with a 400-level error (e.g., 422 Unprocessable Entity if using FastAPI/Pydantic-style validation).
- **Pagination**:
  - A request with `limit=5` returns 5 results.
  - A request with a `limit` greater than the max (100) is capped at 100.
- **Workspace Not Found**: Request with a non-existent `{id}` fails with 404 and `workspace_not_found` error code.
- **Index Not Found**: Mock the RAG service to raise an `IndexNotFoundError` and verify the API returns 503 with `index_not_found` error code.

#### `GET /api/v1/workspaces/{id}/symbols/{name}`
- **Happy Path**: Returns 200 OK for a known symbol.
- **Symbol Not Found**: Mock the RAG service to return `None` or raise an error, and verify the API returns 404 with `symbol_not_found`.
- **Workspace Not Found**: Request with a non-existent `{id}` fails with 404.

#### `GET /api/v1/workspaces/{id}/symbols/{name}/references`
- **Happy Path**: Returns 200 OK for a symbol with known references.
- **Symbol Not Found**: Similar to the above, returns 404.
- **Pagination**: Test the `limit` parameter.

#### `GET /api/v1/workspaces/{id}/symbols/{name}/lineage`
- **Happy Path**: Returns 200 OK for a symbol with a known call graph.
- **Parameters**: Test the `direction` and `depth` parameters to ensure they are passed to the underlying RAG function.
- **Symbol Not Found**: Returns 404.

#### `GET /api/v1/workspaces/{id}/files/{path:path}`
- **Happy Path**: Returns 200 OK for a file known to be in the index. The path should be URL-encoded.
- **File Not Found**: Mock the RAG service to indicate the file is not found; verify a 404 `file_not_found` response.
- **Path Traversal**: Ensure a path like `..%2F..%2Fetc%2Fpasswd` is handled safely and results in a 404 or other appropriate error, not a security leak.

### 5. Recommended Executor

**Demon:** `rem_worker` (Standard Test Implementation Worker)
**Reason:** This is a standard test implementation task requiring `pytest` and `TestClient` knowledge, which falls within the capabilities of a generalist test worker.
