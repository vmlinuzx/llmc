# SDD: Agent Silent Tool Failure

## 1. Gap Description
The `Agent.ask_with_tools` method currently performs a silent check for tool availability based on the current tier.
If the model attempts to call a tool that is not available (e.g., `write_file` while in `WALK` mode), the code simply `continue`s the loop:
```python
if not self.tools.is_tool_available(tc["function"]["name"]):
    # Tool not available, skip
    continue
```
This leaves the model without any feedback. It doesn't know the tool call failed, and typically the loop will terminate or the model will hallucinate that the action was taken. The agent MUST provide feedback to the model that the tool is unavailable/forbidden.

## 2. Target Location
`tests/gap/test_agent_tool_feedback.py`

## 3. Test Strategy
1.  **Setup**:
    -   Instantiate `Agent` with a mock `OllamaBackend`.
    -   Configure `ToolRegistry` to force `ToolTier.WALK` (readonly).
2.  **Execution**:
    -   Mock the backend to return a `ToolCall` for `write_file` (which is a `RUN` tier tool).
    -   Call `agent.ask_with_tools("Please write this file")`.
3.  **Verification**:
    -   Inspect the internal `messages` list (or the returned `AgentResponse` if exposed, but likely need to inspect what was sent back to the model in the *next* turn or check the final response logic).
    -   The most robust way is to check that the agent *did not* silently skip.
    -   **Expected Behavior (after fix)**: The agent loops back to the model with a `tool` role message: `{"role": "tool", "content": "Error: Tool 'write_file' is not available in current tier (WALK)."}`.
    -   **Current Behavior**: The agent skips the tool execution and potentially loops or exits without adding a tool result.
4.  **Refinement**:
    -   Since we are writing a reproduction test, we assert that the failure happens (or rather, we write the test expecting the *correct* behavior, and it will fail, demonstrating the gap).
    -   The test should assert that the "Error: Tool ... not available" message is present in the conversation history passed to the model in the subsequent turn (or strictly, that the tool call resulted in *some* feedback).

## 4. Implementation Details
-   Use `unittest.mock` to mock `OllamaBackend.generate_with_tools`.
-   The mock should yield a response with `tool_calls=[...]` on the first call, and a "I apologize" text response on the second call.
-   Check the arguments passed to the *second* call to `generate_with_tools`. It should contain the tool error message.
