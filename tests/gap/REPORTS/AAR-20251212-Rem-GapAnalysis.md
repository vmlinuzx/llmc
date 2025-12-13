# AAR: Gap Analysis - Rem the Gap Analysis Demon
**Date:** 2025-12-12
**Agent:** Rem (Gap Analysis Variant)
**Topic:** Core Agent Logic & MCP Security

## Mission Summary
Analyzed `llmc_agent` and `llmc_mcp` for logic gaps, stability issues, and security blind spots.
Identified 3 critical gaps and 1 false alarm.
Spawned 4 worker agents to implement reproduction tests.

## Identified Gaps

### 1. Agent Silent Tool Failure (Logic Bug)
-   **Description**: The `ask_with_tools` loop silently ignores tool calls that are not available in the current tier (e.g., calling `write_file` in `WALK` mode). The model receives no feedback and hangs or hallucinates.
-   **SDD**: `tests/gap/SDDs/SDD-Agent-SilentToolFailure.md`
-   **Test**: `tests/gap/test_agent_tool_feedback.py`
-   **Status**: 🔴 CONFIRMED (Test Failed: "Assistant tool call message missing from history")

### 2. Agent Context Overflow (Stability Gap)
-   **Description**: `ask_with_tools` accumulates tool inputs and outputs in the conversation history without pruning or summarization. Long tool loops or large file reads cause context window overflow (`num_ctx`), leading to crashes or silent truncation by the backend.
-   **SDD**: `tests/gap/SDDs/SDD-Agent-ContextOverflow.md`
-   **Test**: `tests/gap/test_agent_context_overflow.py`
-   **Status**: 🔴 CONFIRMED (Test Passed: Asserted that total tokens exceeded budget)

### 3. MCP Edit Block OOM (Security/Stability Vulnerability)
-   **Description**: `llmc_mcp.tools.fs.edit_block` reads the entire target file into memory (`read_text()`) before performing replacement. It lacks the `max_bytes` check present in `read_file`, allowing a malicious or accidental edit of a massive file to OOM the MCP server.
-   **SDD**: `tests/gap/SDDs/SDD-MCP-EditBlock-OOM.md`
-   **Test**: `tests/gap/security/test_mcp_edit_oom.py`
-   **Status**: 🔴 CONFIRMED (Test Failed: Function attempted to read file without error)

### 4. Agent Malformed Arguments (Robustness)
-   **Description**: Suspected crash on invalid JSON from model.
-   **SDD**: `tests/gap/SDDs/SDD-Agent-MalformedToolArgs.md`
-   **Test**: `tests/gap/test_agent_robustness.py`
-   **Status**: 🟢 DISPROVED (Code already handles `Exception` during `json.loads` and returns error feedback).
-   **Note**: Test retained as regression coverage.

## Recommendations
1.  **Fix Agent Feedback**: Modify `llmc_agent/agent.py` to append a tool error message to history when `is_tool_available` returns False.
2.  **Implement Context Pruning**: Update `ask_with_tools` to check `count_tokens` against `config.agent.context_budget` and prune oldest messages or truncate tool outputs.
3.  **Patch MCP Edit Block**: Add `file_size` check to `llmc_mcp/tools/fs.py` before `read_text`.

## Artifacts
-   `tests/gap/SDDs/*`
-   `tests/gap/REPORTS/AAR-20251212-Rem-GapAnalysis.md`
-   `tests/gap/test_*.py`
