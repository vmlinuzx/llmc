# SDD: Filesystem Write Path Traversal

## 1. Gap Description
The current test suite for the `llmc_mcp.tools.fs` module includes checks for path traversal vulnerabilities in read-only operations like `read_file`. However, there is no test coverage to ensure that write operations are similarly protected. The functions `write_file`, `edit_block`, `move_file`, and `delete_file` all rely on `validate_path`, but there are no explicit tests to confirm that this validation is effective when these destructive operations are called with malicious, path-traversal input.

## 2. Target Location
The new tests should be added to the existing security test file:
`tests/security/test_fs_traversal.py`

This keeps all traversal-related security tests in a single, logical location.

## 3. Test Strategy
The strategy is to create new test functions that attempt to perform file-writing and deleting operations outside of the allowed root directory. The tests must confirm that these attempts are blocked before any filesystem modification occurs.

- **For `write_file`:** Attempt to write a file using a path traversal payload (e.g., `../evil.txt`). The test must assert that the function returns a `FsResult` with `success=False` and an error indicating a `PathSecurityError` or that the path is outside allowed roots. It must also verify that the malicious file was not actually created.
- **For `delete_file`:** Create a file outside the allowed root. Attempt to delete it using a path traversal payload. The test must assert that the function fails in the same manner as the write test and that the file still exists after the failed attempt.

## 4. Implementation Details
In `tests/security/test_fs_traversal.py`:

1.  Import the necessary write functions: `from llmc_mcp.tools.fs import write_file, delete_file`.
2.  Create a new test function `test_write_file_traversal_blocked`.
    -   Set up an `allowed_root` and a path to a `malicious_output` file outside that root.
    -   Call `write_file` with a traversal path like `str(allowed_root / "../malicious.txt")`.
    -   Assert `result.success is False`.
    -   Assert that a security-related error message is in `result.error`.
    -   Assert that the `malicious_output` path does not exist on disk.
3.  Create a new test function `test_delete_file_traversal_blocked`.
    -   Set up an `allowed_root` and create a `target_file` outside of it.
    -   Call `delete_file` with a traversal path pointing to the `target_file`.
    -   Assert `result.success is False`.
    -   Assert that a security-related error message is in `result.error`.
    -   Assert that the `target_file` still exists.
