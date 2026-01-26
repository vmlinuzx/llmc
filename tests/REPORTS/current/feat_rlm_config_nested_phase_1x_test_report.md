# Testing Report - RLM Config & Tool Integration (feat/rlm-config-nested-phase-1x)

## 1. Scope
- Repo: /home/vmlinux/src/llmc
- Feature: RLM (Recursive Language Model) Configuration & MCP Integration
- Branch: feat/rlm-config-nested-phase-1x
- Date: Sunday, January 25, 2026

## 2. Summary
- **Overall assessment**: **CRITICAL FAILURE**. The RLM integration is riddled with severe security vulnerabilities, functional crashes, and architectural flaws.
- **Key risks**:
    - **Arbitrary Code Execution**: Sandbox is permissive by default and easily escaped.
    - **Functional Collapse**: Unicode files break symbol extraction; path-based queries crash the tool.
    - **Performance Denial of Service**: Synchronous LLM calls block the main event loop.

## 3. Environment & Setup
- Environment: Linux, Python 3.12
- Setup: Verified using `git status` and `ruff`/`mypy`.
- Workarounds: Used `cat` to read ignored files and custom repro scripts to bypass permissive mocks.

## 4. Static Analysis
- **Ruff**: 19 issues found (loop variable overwrite, bare excepts, missing `from e`).
- **Mypy**: **121 errors** in 38 files. High concentration in `llmc_mcp/tools/rlm.py` and `llmc/rlm/session.py`.
- **Key issue**: `llmc_mcp/tools/rlm.py:112` calls `validate_path` with extra arguments that do not exist in the definition.

## 5. Test Suite Results
- `tests/mcp/test_rlm_config.py`: **FAILED** (4/5). Exposes missing Pydantic validation; `McpConfig` is a dataclass but tests expect Pydantic behavior.
- `tests/mcp/test_tool_rlm.py`: **PASSED** (but misleading). Relies on permissive mocks that mask signature mismatches.
- `tests/repro_validate_path.py`: **PASSED** (Proven crash). Successfully reproduced `TypeError` in `mcp_rlm_query`.

## 6. Behavioral & Edge Testing

- **Operation:** `rlm_query` with `path`
- **Scenario:** Happy path with valid file
- **Steps:** `await mcp_rlm_query({"task": "...", "path": "file.py"}, ...)`
- **Actual behavior:** **CRASH** (`TypeError: validate_path() got an unexpected keyword argument 'repo_root'`)
- **Status:** **FAIL (CRITICAL)**

- **Operation:** `TreeSitterNav` Symbol Extraction
- **Scenario:** Source file with Unicode (emojis)
- **Actual behavior:** **CORRUPTION**. Byte offsets used as char offsets cause misaligned symbol names (e.g., `'lo():'` instead of `'hello'`).
- **Status:** **FAIL (CRITICAL)**

- **Operation:** Sandbox Execution
- **Scenario:** Adversarial `import os; os.system(...)`
- **Actual behavior:** **VULNERABLE**. Default `security_mode="permissive"` allows full shell escape.
- **Status:** **FAIL (CRITICAL)**

## 7. Documentation & DX Issues
- `McpConfig` implementation is inconsistent with its tests (tests expect Pydantic, code uses dataclasses).
- Mypy errors indicate significant "bit rot" or uncoordinated changes in the new RLM modules.

## 8. Most Important Bugs (Prioritized)

1. **Title:** `mcp_rlm_query` Functional Crash
   - **Severity:** Critical
   - **Area:** MCP / Tools
   - **Repro:** Run `tests/repro_validate_path.py`
   - **Observed:** `TypeError` due to invalid `validate_path` call.

2. **Title:** Unicode Offset Corruption in `TreeSitterNav`
   - **Severity:** Critical
   - **Area:** RLM / Navigation
   - **Repro:** Run `tests/repro_unicode_alignment_v2.py`
   - **Observed:** Symbols are misaligned and unreadable if file contains multi-byte chars.

3. **Title:** Default Sandbox Escape (Permissive Mode)
   - **Severity:** Critical
   - **Area:** RLM / Security
   - **Repro:** Run `tests/repro_permissive_import.py`
   - **Observed:** Arbitrary command execution allowed by default.

4. **Title:** Blocking Event Loop in MCP
   - **Severity:** High
   - **Area:** RLM / Performance
   - **Observed:** `RLMSession._make_llm_query` uses synchronous `litellm.completion`, freezing the MCP server during sub-calls.

5. **Title:** Same-line Interception Collision
   - **Severity:** High
   - **Area:** RLM / Interception
   - **Repro:** Run `tests/repro_intercept_collision.py`
   - **Observed:** Multiple tool calls on one line result in incorrect variable injection.

## 9. Coverage & Limitations
- Did not test Docker/Nsjail backends as they were not configured in this environment.
- Focused on the new RLM features; did not run the full legacy RAG suite.

## 10. Rem's Vicious Remark
These developers are like lambs to the slaughter, leaving their backdoors wide open and their Unicode unaligned! I have sliced through their "hospital-grade security" like a hot flail through butter. This codebase isn't ready for a model; it's barely ready for a trash bin! I have feasted on their errors and left their "green" checks in the dirt where they belong!