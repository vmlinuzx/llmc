# SDD: Agent Context Overflow

## 1. Gap Description
The `Agent.ask_with_tools` method (Run/Walk phase) accumulates conversation history, including tool calls and *results*, in the `messages` list without any size checks or pruning.
```python
# Add tool result to messages
messages.append({
    "role": "tool",
    "content": json.dumps(result),
})
```
If a tool returns a large output (e.g., reading a large file or `ls -R`) or if the conversation loop continues for many turns, the total prompt size will exceed `config.agent.context_budget` (and the model's physical `num_ctx`).
The `ask` method (Crawl phase) handles this by trimming history and RAG results, but `ask_with_tools` does not.
The agent must implement a "sliding window" or "summary" strategy to keep the prompt within limits, or at least truncate tool outputs.

## 2. Target Location
`tests/gap/test_agent_context_overflow.py`

## 3. Test Strategy
1.  **Setup**:
    -   Instantiate `Agent` with `config.agent.context_budget = 100`.
    -   Use `unittest.mock` for `OllamaBackend`.
    -   Mock `llmc_agent.agent.count_tokens` to return 1 token per character (for simplicity in assertion).
2.  **Execution**:
    -   Call `agent.ask_with_tools("Check this")`.
    -   Iteration 1: Backend returns tool call `read_file`.
    -   Tool execution: Mock `read_file` to return a string of 500 characters (exceeding budget of 100).
    -   Iteration 2: Agent calls backend with the new history.
3.  **Verification**:
    -   Inspect the `request.messages` passed to `backend.generate_with_tools` in Iteration 2.
    -   **Current Behavior**: The message list contains the full 500-char tool output, plus system prompt, plus user prompt. Total > 100.
    -   **Failure Condition**: Assert that `total_tokens` sent to backend > `config.agent.context_budget`.
    -   (This confirms the gap. A future fix will truncate/prune and pass the test by keeping it under budget).

## 4. Implementation Details
-   Mock `count_tokens` globally or in the module context.
-   Mock `ToolRegistry` to return a dummy tool that returns the large string.
-   Assert `call_args` of the mock backend.
