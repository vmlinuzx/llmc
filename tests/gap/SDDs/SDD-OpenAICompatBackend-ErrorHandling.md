# SDD: OpenAICompatBackend-ErrorHandling

## 1. Gap Description
The `OpenAICompatBackend` in `llmc_agent/backends/openai_compat.py` currently uses a generic `response.raise_for_status()` to handle HTTP errors. This does not provide granular error handling for different failure modes (e.g., 401 Unauthorized, 429 Too Many Requests, 500 Internal Server Error). The client is not resilient and cannot react intelligently to different types of server-side problems.

## 2. Target Location
A new test file should be created at `tests/agent/test_openai_compat_backend.py`. The existing `llmc_agent/backends/` directory does not have any tests.

## 3. Test Strategy
We will use `pytest` and the `httpx` mocking library (`respx`) to simulate different HTTP error responses from the OpenAI-compatible API. We will create a test fixture for the `OpenAICompatBackend` instance and then write individual tests to assert that the correct exceptions are raised for each HTTP status code.

- **Test Case 1: 401 Unauthorized:** The backend should raise a specific `AuthenticationError`.
- **Test Case 2: 429 Too Many Requests:** The backend should raise a `RateLimitError`.
- **Test Case 3: 500 Internal Server Error:** The backend should raise a `APIError` or `InternalServerError`.
- **Test Case 4: 404 Not Found:** The backend should raise a `NotFoundError`.

## 4. Implementation Details
- Create a new test file: `tests/agent/test_openai_compat_backend.py`.
- Import `pytest`, `httpx`, `respx`, and `OpenAICompatBackend`.
- Define custom exception classes if they don't already exist (e.g., `AuthenticationError`, `RateLimitError`). These should probably be defined in a central `llmc_agent.exceptions` module. For the purpose of this test, they can be defined locally in the test file if needed.
- Use `respx.mock` to mock the `POST` request to `http://localhost:8080/v1/chat/completions`.
- For each test case, configure the mock response with the desired HTTP status code.
- Call the `generate` method on the `OpenAICompatBackend` instance within a `pytest.raises` context manager.
- Assert that the expected exception is raised.
- Repeat for `generate_stream` and `generate_with_tools`.
