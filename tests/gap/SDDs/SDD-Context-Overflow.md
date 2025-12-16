# SDD: Unbounded Tool Output Context Overflow

## 1. Gap Description
The `llmc_agent` execution loop (`Agent.ask_with_tools`) receives output from tools and appends it directly to the message history without checking its size or enforcing a token limit.

If a tool returns a very large result (e.g., `read_file` on a large log file, or `list_dir` on a huge directory), the accumulated message history will exceed the context window of the LLM (or the API's limit). This causes the subsequent `ollama.generate_with_tools` call to fail, crashing the agent conversation.

## 2. Target Location
`tests/gap/test_agent_context_overflow.py`

## 3. Test Strategy
We need to demonstrate that a large tool output causes the agent to crash or fail to proceed.

1.  **Mocking**:
    *   Mock `OllamaBackend` to simulate the conversation.
    *   Mock `ToolRegistry` or a specific tool to return a massive string (e.g., 100k tokens worth of text).
    *   Set `AgentConfig.context_budget` to a small value (e.g., 4000 tokens) to make it easy to overflow.

2.  **Test Case**:
    *   Configure `Agent` with a small context budget.
    *   Register a "VerboseTool" that returns a string longer than the budget.
    *   Mock the LLM to call `VerboseTool` in the first round.
    *   Call `agent.ask_with_tools("read the big file")`.
    *   **Assertion**: The call to `agent.ask_with_tools` raises an error (likely from the backend mock or the agent loop itself if it had checks), OR we assert that the `messages` list sent to the backend in the *second* round contains the massive string, proving the lack of truncation.
    *   Since we are mocking the backend, we can simply assert on the *arguments passed to the backend* in the second round. If the message history sent to the backend is huge, the gap is proven.

## 4. Implementation Details
*   Create `tests/gap/test_agent_context_overflow.py`.
*   Define a helper `make_agent_with_mock_backend`.
*   Mock `OllamaBackend.generate_with_tools`.
*   First call to `generate` returns a tool call to `verbose_tool`.
*   `verbose_tool` returns a string of length 50,000 chars.
*   The loop proceeds to call `generate` a second time.
*   Capture the `messages` passed to the second `generate` call.
*   Assert that the tool output message content length is 50,000.
*   (If the code *was* correct, it would be truncated to ~4000 chars or similar).
