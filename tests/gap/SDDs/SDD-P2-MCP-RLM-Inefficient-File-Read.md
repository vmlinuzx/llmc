# SDD: P2-MCP-RLM-Inefficient-File-Read

## 1. Gap Description
**Severity:** P2 (Medium)

In `llmc_mcp/tools/rlm.py`, the code to read and truncate a file is:
```python
file_text = resolved_path.read_text(errors="replace")[:max_bytes]
```
This reads the entire file content into memory before slicing the first `max_bytes`. If a file is significantly larger than the `max_bytes` limit (e.g., a 1GB log file with a 1MB limit), this can cause excessive memory consumption, potentially leading to performance degradation or termination of the MCP process.

## 2. Target Location
- **File:** `llmc_mcp/tools/rlm.py`

## 3. Test Strategy
A unit test should be created to verify the fix.
1.  Use `pyfakefs` to create a large file (e.g., 10MB).
2.  Set a small `max_bytes` limit (e.g., 1KB).
3.  Mock the `Path.open` method (or a lower-level file operation) to assert that the `read()` call is invoked with a size argument, rather than reading the whole file.
4.  Verify that the returned text has the correct truncated length.

## 4. Implementation Details
The implementation should be changed to read only the required number of bytes.

**Current Code:**
```python
file_text = resolved_path.read_text(errors="replace")[:max_bytes]
```

**Recommended Fix:**
```python
file_text = ""
with resolved_path.open("r", errors="replace") as f:
    file_text = f.read(max_bytes)
```
This approach is more memory-efficient as it instructs the file handler to read at most `max_bytes` from the file stream, avoiding loading the entire file into memory.
