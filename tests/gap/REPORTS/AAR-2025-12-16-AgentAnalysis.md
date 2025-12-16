# Gap Analysis Report: LLMC Agent

**Date**: 2025-12-16
**Analyst**: Rem (Gap Analysis Demon)
**Scope**: `llmc_agent` package (Agent Logic & Tools)

## Summary
A targeted gap analysis was performed on the `llmc_agent` package, specifically focusing on the `Agent.ask_with_tools` execution loop. Two critical vulnerabilities were identified and proven with reproduction test cases.

## Identified Gaps

### 1. Safety Confirmation Bypass (CRITICAL)
- **Description**: The agent completely ignores the `requires_confirmation=True` flag defined on destructive tools (like `write_file`, `edit_block`).
- **Impact**: The agent can modify or delete files on the user's filesystem without any human intervention or approval, posing a severe safety risk.
- **SDD**: `tests/gap/SDDs/SDD-Safety-ConfirmationBypass.md`
- **Proof of Concept**: `tests/gap/test_security_confirmation_bypass.py`
- **Status**: **VULNERABILITY CONFIRMED**. The test case demonstrates that a sensitive tool is executed immediately by the agent loop.

### 2. Unbounded Tool Output Context Overflow (HIGH)
- **Description**: The agent appends tool outputs (e.g., from `read_file`) directly to the message history without any size validation or truncation.
- **Impact**: Reading a large file or listing a large directory will cause the message history to exceed the context window of the LLM or API, causing the agent to crash on the subsequent generation step. This creates a denial-of-service condition for the agent session.
- **SDD**: `tests/gap/SDDs/SDD-Context-Overflow.md`
- **Proof of Concept**: `tests/gap/test_agent_context_overflow.py`
- **Status**: **GAP CONFIRMED**. The test case demonstrates that a 50,000-character string is passed untruncated to the backend, exceeding the configured budget.

## Recommendations

1.  **Fix Safety Bypass**:
    - Modify `Agent.ask_with_tools` in `llmc_agent/agent.py`.
    - Before executing a tool, check `tool.requires_confirmation`.
    - If True, either pause execution and request user input (if interactive) or raise a `ConfirmationRequired` error that the UI can handle.
    - *Immediate Action*: Do not allow the agent to run destructive tools until this is fixed.

2.  **Fix Context Overflow**:
    - Modify `Agent.ask_with_tools` in `llmc_agent/agent.py`.
    - Before appending tool output to `messages`, use `llmc_agent.prompt.trim_to_budget` (or similar logic) to truncate the output if it exceeds a reasonable limit (e.g., 2000-4000 tokens).
    - Add a "truncated" notice to the content so the model knows data is missing.

## Artifacts Created
- `tests/gap/SDDs/SDD-Safety-ConfirmationBypass.md`
- `tests/gap/SDDs/SDD-Context-Overflow.md`
- `tests/gap/test_security_confirmation_bypass.py`
- `tests/gap/test_agent_context_overflow.py`
