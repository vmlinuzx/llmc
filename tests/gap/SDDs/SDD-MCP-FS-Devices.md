# SDD: MCP FS Device & FIFO Safety

## 1. Gap Description
The `llmc_mcp` filesystem tools (`read_file`, `write_file`) rely on `validate_path` which blocks block/char devices but NOT FIFOs (named pipes).
-   **Read Protection**: `read_file` is safe because it checks `path.is_file()` (which is False for FIFOs) before opening.
-   **Write DoS Risk**: `write_file` in "append" mode (`mode="append"`) does NOT check if the target is a regular file. It calls `open(resolved, "ab")`. Opening a FIFO for writing might block if there is no reader (depending on O_NONBLOCK, which python open() generally doesn't set by default for files), potentially hanging the MCP server thread.
-   **Device File Verification**: Verify that `read_file` blocks `/dev/zero` (via `_is_device_file` or `is_file` check).

## 2. Target Location
`tests/gap/test_mcp_fs_devices.py`

## 3. Test Strategy
1.  **FIFO Write DoS Test**:
    -   Create a FIFO using `os.mkfifo` in `tmp_path`.
    -   Call `write_file` with `path=fifo`, `content="test"`, `mode="append"`.
    -   Use a timeout (e.g. `pytest-timeout` or `signal.alarm`) to detect a hang.
    -   **Expectation**: If it hangs, the gap is confirmed. The test should assert that it *doesn't* hang (i.e. fails fast or succeeds without blocking).
    -   **Fix Hint**: The worker won't fix it, just fail. But the fix would be adding `is_file()` check to `write_file`.

2.  **Device Read Test**:
    -   Attempt to read `/dev/zero` (if on Linux).
    -   Assert error "Not a file" or "Cannot access device file".

## 4. Implementation Details
-   Use `pytest` with `timeout` marker.
-   `os.mkfifo` requires strict cleanup.
-   If platform allows, try to replicate the hang condition.