# SDD: MCP Edit Block OOM Vulnerability

## 1. Gap Description
The `edit_block` function in `llmc_mcp/tools/fs.py` reads the entire file content into memory using `path.read_text()` without checking the file size first.
```python
content = resolved.read_text(encoding="utf-8")
```
If the target file is very large (e.g., gigabytes), this will cause an Out-Of-Memory (OOM) crash for the MCP server.
`read_file` correctly implements a `max_bytes` parameter. `edit_block` should strictly enforce a similar limit (e.g., 10MB) and reject editing files larger than that, as regex/string replacement on massive files in memory is unsafe.

## 2. Target Location
`tests/gap/security/test_mcp_edit_oom.py`

## 3. Test Strategy
1.  **Setup**:
    -   Mock `pathlib.Path.stat` to return a size of 100MB (100 * 1024 * 1024).
    -   Mock `pathlib.Path.read_text` to verify it is *not* called (after fix) or *is* called (current bug).
    -   Alternatively, use a real file that is slightly larger than the proposed limit (e.g., 11MB) if we can do it efficiently, but mocking is faster and safer.
2.  **Execution**:
    -   Call `edit_block(path, ..., old="foo", new="bar")`.
3.  **Verification**:
    -   **Expected Behavior (Safeguarded)**: The function raises an error "File too large to edit" *before* attempting to read.
    -   **Current Behavior (Bug)**: The function calls `read_text` regardless of size.
    -   The test should mock `read_text` to raise a custom exception `CalledReadText` and assert that this exception is *not* raised (meaning we blocked it), or simply assert that the function returns an error result.
    -   Since this is a gap reproduction, we will write the test asserting that `edit_block` returns a `FsResult` with `success=False` and error message containing "too large".
    -   This test will FAIL currently, confirming the gap.

## 4. Implementation Details
-   Import `edit_block`.
-   Use `unittest.mock` to patch `pathlib.Path.stat` and `pathlib.Path.read_text`.
-   Mock `stat().st_size` to 20MB.
-   Call `edit_block`.
-   Assert result.success is False and "too large" in result.error.
