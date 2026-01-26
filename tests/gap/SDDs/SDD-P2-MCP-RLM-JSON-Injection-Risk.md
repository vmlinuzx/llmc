# SDD: P2-MCP-RLM-JSON-Injection-Risk

## 1. Gap Description
**Severity:** P2 (Medium)

The generic exception handler in `llmc_mcp/tools/rlm.py` directly embeds a raw exception message into the JSON error response:
```python
except Exception as e:
    # ...
    return {
        "error": f"Internal error: {type(e).__name__}: {e}",
        "meta": {
            "error_code": "internal_error",
            "retryable": True,
            "traceback": traceback.format_exc()[:500]
        }
    }
```
While `json.dumps` on the server side will likely escape double quotes, including raw, unprocessed exception data in a response is a potential security risk. A maliciously crafted exception (or an unexpected one from a library) could contain characters that might be misinterpreted by downstream clients or logging systems, potentially leading to log injection or other minor vulnerabilities. It is better to return a generic error message or a heavily sanitized one.

## 2. Target Location
- **File:** `llmc_mcp/tools/rlm.py`

## 3. Test Strategy
A unit test can be written to trigger the generic `except Exception` block with a custom exception that has a malicious-looking payload.

1.  Mock the `RLMSession.run` method to raise a custom exception: `raise Exception('{"key": "value"}')`.
2.  Call `mcp_rlm_query`.
3.  Assert that the `error` field in the returned dictionary does *not* contain the raw exception string, but rather a safe, generic message.

## 4. Implementation Details
The implementation should avoid including the raw exception `e` in the final error string.

**Current Code:**
```python
return {
    "error": f"Internal error: {type(e).__name__}: {e}",
    # ...
}
```

**Recommended Fix (Option 1 - Generic Message):**
```python
import logging
logging.exception("RLM internal error") # Log the full exception for debugging
return {
    "error": "An unexpected internal error occurred in the RLM tool.",
    "meta": {
        "error_code": "internal_error",
        "retryable": True,
    }
}
```
This is the safest option. The detailed error is logged on the server for maintainers, but the client receives a simple, safe message.

**Recommended Fix (Option 2 - Sanitized Message):**
If some detail is desired, ensure it's sanitized.
```python
error_type = type(e).__name__
error_msg = str(e).translate(str.maketrans({"'" :  r'\"', "\"": r'\\\' }))
return {
    "error": f"Internal error: {error_type}",
    "meta": {
        "error_code": "internal_error",
        "retryable": True,
        "detail": error_msg[:200] # Truncate for safety
    }
}
```
Option 1 is strongly preferred for security.

```