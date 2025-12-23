# SDD: Error Handling in get_repo_stats

## 1. Gap Description
The `get_repo_stats` function in `llmc/cli.py` has a broad `except Exception` block that catches any error and may obscure specific issues. This makes it difficult to debug problems and could lead to unexpected behavior.

This SDD describes the tests required to validate the error handling in `get_repo_stats`.

## 2. Target Location
`tests/cli/test_cli.py`

## 3. Test Strategy
The tests will use `pytest` and `unittest.mock` to simulate different error conditions and verify that `get_repo_stats` handles them correctly. The tests will cover the following scenarios:
- **`_load_graph` returns an unexpected data structure:** Mock `_load_graph` to return invalid data and verify that `get_repo_stats` handles the error gracefully.
- **`load_status` raises an exception:** Mock `load_status` to raise a specific exception and verify that `get_repo_stats` catches it and sets the appropriate error state.
- **`_load_graph` raises an exception:** Mock `_load_graph` to raise an exception and verify that `get_repo_stats` catches it and sets the appropriate error state.

## 4. Implementation Details
The test implementation will require the following:
- A new test file `tests/cli/test_cli.py`.
- `pytest` fixtures to create a temporary repository root and mock the dependencies of `get_repo_stats`.
- Test cases for each of the scenarios described in the Test Strategy.
- Assertions that `get_repo_stats` returns the expected error state for each scenario.
