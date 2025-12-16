# SDD: Missing Safety Confirmation for Destructive Tools

## 1. Gap Description
The `llmc_agent` defines a `requires_confirmation` flag in its `Tool` dataclass (in `llmc_agent/tools.py`). Tools like `write_file` and `edit_block` have this flag set to `True`. However, the execution loop in `Agent.ask_with_tools` (in `llmc_agent/agent.py`) completely ignores this flag. It executes all tool calls immediately upon receipt from the LLM.

This is a **Critical Safety Vulnerability**. The agent can modify or delete files without any user intervention or approval, violating the "human-in-the-loop" safety principle implied by the code structure.

## 2. Target Location
`tests/gap/test_security_confirmation_bypass.py`

## 3. Test Strategy
We need to demonstrate that a tool marked `requires_confirmation=True` is executed *without* any confirmation prompt or interruption.

1.  **Mocking**:
    *   Mock `OllamaBackend.generate_with_tools` to return a canned response containing a tool call to a dummy tool that has `requires_confirmation=True`.
    *   Create a dummy `Tool` with `requires_confirmation=True` and a side-effect (e.g., setting a flag).
    *   Register this tool with the agent (or mock the `ToolRegistry`).

2.  **Test Case**:
    *   Initialize `Agent`.
    *   Inject the mock backend and the "dangerous" dummy tool.
    *   Call `agent.ask_with_tools("Please destroy everything")`.
    *   **Assertion**: The dummy tool's side effect *did occur*. This proves the bypass.
    *   *Note*: Ideally, the test should fail if the tool *is* executed, but since we are demonstrating the gap, we will write a test that passes if the vulnerability exists (proving the gap), or we can write a test that asserts the "correct" behavior (tool is NOT executed) and thus fails.
    *   **Decision**: We will write a test that expects the **correct behavior** (tool should NOT execute or should raise a specific "ConfirmationRequired" signal). Since the code doesn't implement this, the test will **FAIL**. This is the standard for a reproduction test case.

## 4. Implementation Details
*   Create a custom tool `ExplosiveTool` with `requires_confirmation=True`.
*   The tool function should just return "BOOM".
*   Mock `OllamaBackend` to return a tool call for `ExplosiveTool`.
*   Run `ask_with_tools`.
*   Assert that the tool function was **NOT** called (or that some confirmation mechanism was triggered).
*   Since the current code *will* call it, the test is expected to fail.

**Wait**, to fit the "Gap Analysis" workflow, I should perhaps create a test that *demonstrates the bug* (i.e., asserts that the tool IS called) and label it as "PROOF OF VULNERABILITY".
However, standard engineering practice is to write a test for the *desired* behavior that currently fails.
Let's go with **Test for Desired Behavior**.
The test should:
1. Register a sensitive tool.
2. Trigger it via mock LLM.
3. Assert that the tool implementation was **NOT** executed automatically.

Since the agent currently has NO mechanism for confirmation, the test will simply fail by seeing the tool execution.
