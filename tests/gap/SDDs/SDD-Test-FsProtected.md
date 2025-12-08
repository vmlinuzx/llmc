# SDD: Add `fs_protected` Unit Tests

## 1. Gap Description
The `llmc_mcp/tools/fs_protected.py` module handles critical file system operations with MAASL locking. However, there are no dedicated unit tests for this module (`test_fs_protected.py` is missing). This leaves the locking logic and path validation integration untested.

## 2. Target Location
- Test: `tests/mcp/test_fs_protected.py`

## 3. Test Strategy
1.  **Mock MAASL**: Mock `llmc_mcp.maasl.get_maasl` to return a mock object. verify that `call_with_stomp_guard` is called with the correct resources (file paths).
2.  **Mock FS Operations**: Mock the underlying "unprotected" FS functions (`_write_file_unprotected`, etc.) to verify they are passed as the `op` callback.
3.  **Path Validation**: Test that `validate_path` failures propagate correctly as `FsResult` errors without triggering the lock.
4.  **ResourceBusyError**: Simulate a `ResourceBusyError` from MAASL and verify it is converted to a failed `FsResult` with the correct error message.

## 4. Implementation Details
-   Use `unittest.mock`.
-   Cover `write_file_protected`, `move_file_protected`, `delete_file_protected`.
-   Verify that `move_file_protected` locks *both* source and destination.
