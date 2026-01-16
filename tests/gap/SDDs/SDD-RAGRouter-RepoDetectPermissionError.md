# SDD: RAG Router Repo Detection PermissionError

## 1. Gap Description
The `llmc.rag_router.route_query` convenience function contains logic to automatically detect the repository root by traversing parent directories and searching for a `.git` folder.

This traversal logic does not gracefully handle `PermissionError` exceptions. If the script is executed from a location where it lacks permissions to access a parent directory, the `Path.parent` property can raise a `PermissionError`, causing the application to crash.

The current tests mock the `Path` object in a way that doesn't simulate this specific failure mode, leaving a gap in coverage for this important real-world scenario.

## 2. Target Location
The new test should be added to the test file for the RAG router: `tests/test_rag_router.py`. It should be placed within the `TestRouteQueryConvenienceFunction` class.

## 3. Test Strategy
The test will use `unittest.mock.patch` to mock the `Path.parent` property. The mock will be configured to raise a `PermissionError` when accessed. The test will then call `route_query` from a simulated non-root directory and assert two things:
1. The function does not crash (i.e., the `PermissionError` is caught).
2. The function gracefully falls back to using the current working directory (`Path.cwd()`) as the `repo_root`.

## 4. Implementation Details
- Add a new test method named `test_route_query_auto_detects_repo_root_permission_error`.
- Use `@patch("llmc.rag_router.Path")` to mock the `pathlib.Path` class within the `rag_router` module's scope.
- Configure the mock `Path.cwd()` to return a specific temporary path.
- Configure the `parent` property of the mock `Path` instance to raise a `PermissionError`. A `PropertyMock` can be useful here.
- The `.git` check (`marker.exists()`) should be mocked to return `False` to ensure the parent traversal logic is triggered.
- Call `route_query("test query")` without a `repo_root`.
- In the `route_query` function, the `RAGRouter` is initialized. The test should assert that `RAGRouter` was instantiated with the path returned by `Path.cwd()`, demonstrating the fallback mechanism worked correctly.
