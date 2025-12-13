# SDD: Agent Malformed Tool Arguments

## 1. Gap Description
The `Agent.ask_with_tools` method blindly parses tool arguments using `json.loads` if they are strings:
```python
args = tc["function"]["arguments"]
if isinstance(args, str):
    args = json.loads(args)
```
If the LLM generates invalid JSON (common with weaker models or complex prompts), `json.loads` raises a `JSONDecodeError`. This exception is caught by the broad `except Exception as e` block, but reliance on the generic catch block for expected parsing errors is brittle, and we need to ensure the error message sent back to the model is helpful ("Invalid JSON arguments") rather than a generic Python stack trace or crash if the exception handling isn't robust enough (though currently it catches `Exception`, so it *should* be safe, but we need to verify it actually works and provides good feedback).
More importantly, if `args` is `None` or some other non-iterable, it might fail before the try/except if logic changes.
The primary gap here is verifying that the agent *robustly* handles this and the session survives.

## 2. Target Location
`tests/gap/test_agent_robustness.py`

## 3. Test Strategy
1.  **Setup**:
    -   Instantiate `Agent` with mock backend.
2.  **Execution**:
    -   Mock backend returns a tool call with `arguments: "{ unquoted_key: 5 }"` (invalid JSON).
3.  **Verification**:
    -   Call `ask_with_tools`.
    -   Verify the code does not raise an exception.
    -   Verify that the message sent back to the model (in the next loop or session history) contains a readable error about JSON parsing, allowing the model to correct itself.
    -   Assert `messages[-1]["content"]` contains "JSONDecodeError" or similar.

## 4. Implementation Details
-   Mock `OllamaBackend.generate_with_tools`.
-   Return a `GenerateResponse` with a malformed tool call.
-   Assert the `tool` message content string in the history contains "error" and the specific parsing issue.
