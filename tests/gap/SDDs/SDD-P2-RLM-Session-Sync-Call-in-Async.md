# SDD: P2-RLM-Session-Sync-Call-in-Async

## 1. Gap Description
**Severity:** P2 (Medium)

The `_make_llm_query` method in `llmc/rlm/session.py` is intended to create a tool that can be used within the RLM session. This method uses `litellm.completion` (the synchronous version) to make the LLM call.
```python
response = litellm.completion(
    model=self.config.sub_model,
    messages=[{"role": "user", "content": prompt}],
    # ...
)
```
Although the `llm_query` tool is currently disabled, if it were enabled and called from within the main `async def run(...)` loop (which is asynchronous), this synchronous call would block the entire asyncio event loop. This would prevent any other concurrent tasks from running, hurting performance and responsiveness. The correct implementation should use the asynchronous `litellm.acompletion`.

## 2. Target Location
- **File:** `llmc/rlm/session.py`

## 3. Test Strategy
A test for this would be part of the larger `tests/rlm/test_session.py` suite (from SDD `P1-RLM-Session-Tests`).

1.  Enable the `llm_query` tool during test setup.
2.  Create a test that runs a session where the model is prompted to use `llm_query`.
3.  Mock `litellm.completion` and `litellm.acompletion`.
4.  Assert that `litellm.acompletion` is called and that `litellm.completion` is *not* called.
5.  Alternatively, create a dedicated async test that runs the `llm_query` tool alongside another small async task (e.g., `asyncio.sleep(0.1)`) and measures the execution time to ensure it does not block.

## 4. Implementation Details
The fix is to change the `llm_query` inner function to be `async` and to use `await litellm.acompletion`. This will require the sandbox execution environment to support `await`. Assuming the sandbox can handle async functions, the change would be:

**Current Problematic Structure:**
```python
def llm_query(prompt: str, max_tokens: int = 1024) -> str:
    # ...
    response = litellm.completion(...)
    # ...
    return content
```

**Recommended Fix:**
The sandbox environment (`llmc/rlm/sandbox/process_sandbox.py`) would need to be updated to handle `async` callbacks. If the `execute` method can `await` an `async` function, the fix is straightforward.

In `llmc/rlm/session.py`:
```python
async def llm_query(prompt: str, max_tokens: int = 1024) -> str:
    # ...
    response = await litellm.acompletion(...)
    # ...
    return content
```
The sandbox's `execute` method would then need to `await` the result of this coroutine if it is called. If the sandbox *cannot* support async callbacks, then `llm_query` would need to be run in a separate thread using `asyncio.to_thread` to avoid blocking the main event loop.

```python
# Alternative if sandbox doesn't support async
import asyncio

def llm_query_sync_wrapper(prompt: str, max_tokens: int = 1024) -> str:
    async def do_query():
        # ... (all the async logic)
        response = await litellm.acompletion(...)
        return response.choices[0].message.content

    # This is a sync-over-async call, not ideal but better than blocking
    return asyncio.run(do_query())
```
The best solution is to make the sandbox async-aware.
