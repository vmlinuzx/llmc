# SDD: RAGClient Untested Search Method

## 1. Gap Description
The `llmc.client.RAGClient` class serves as a primary facade for interacting with the RAG system. However, its test coverage is critically low. The `search()` method, a primary entry point for RAG queries, is completely untested.

This gap means there are no regressions checks to ensure that the client correctly initializes, receives arguments, and passes them to the underlying `tool_rag_search` implementation.

## 2. Target Location
The new test should be added to the existing, sparse test file for the client: `tests/test_rag_client.py`.

## 3. Test Strategy
The test will use `unittest.mock.patch` to mock the `llmc.client.tool_rag_search` function. It will then instantiate the `RAGClient`, call the `search()` method with a sample query and a limit, and assert that the mocked `tool_rag_search` was called exactly once with the expected arguments (`repo_root`, `query`, `limit`).

This approach isolates the client's logic from the underlying tool's implementation, ensuring the test is a true unit test of the facade method.

## 4. Implementation Details
- Add a new test method `test_search_calls_underlying_tool` to the `TestRAGClient` class in `tests/test_rag_client.py`.
- Decorate the method with `@patch('llmc.client.tool_rag_search')`.
- Inside the test:
  - Define a fake `repo_root` path.
  - Instantiate `client = RAGClient(repo_root)`.
  - Define a `query = "test query"` and `limit = 10`.
  - Call `client.search(query, limit=limit)`.
  - Use `mock_tool_search.assert_called_once_with(repo_root, query, limit)`.
- A separate test, `test_search_handles_no_limit`, should also be added to ensure that calling `search` without a limit correctly passes `None` to the underlying tool.
