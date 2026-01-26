# Testing Report - RLM Deep Dive & Security Audit

## 1. Scope
- Repo / project: llmc
- Feature / change under test: Recursive Language Model (RLM) Phase 1.1.1
- Commit / branch: feat/rlm-config-nested-phase-1x
- Date / environment: Sunday, January 25, 2026 / Linux (User setup)

## 2. Summary
- **Overall assessment**: **CRITICAL SECURITY REGRESSION**. While the core RLM logic works for "Happy Path" scenarios (43/43 tests passing), the implementation has introduced multiple critical security holes that allow arbitrary file disclosure and remote code execution on the host machine.
- **Key risks**:
    - **Path Traversal**: Any file on the system readable by the user can be leaked into the LLM context.
    - **Sandbox Escape**: The "permissive" default mode allows importing `os` and `subprocess` to execute commands on the host.
    - **Budget Bypass**: Token estimation is easily tricked by Unicode-dense inputs, leading to potential "Denial of Wallet".
    - **Config Safety**: `McpConfig` lacks the validation expected by its own test suite.

## 3. Environment & Setup
- Baseline: `feat/rlm-config-nested-phase-1x` (with uncommitted changes)
- Setup: urllib3 conflict resolved in `pyproject.toml` (v2.6.0 -> v2.3.0).
- Tooling: `ruff`, `mypy`, `pytest`, `rlm_query` (MCP).

## 4. Static Analysis
- **Ruff**: 338 errors found.
    - 80 cases of `B904` (raise without from)
    - 40 cases of `F841` (unused variables)
    - 19 bare excepts (`E722`)
- **Mypy**: 350 errors in 97 files.
    - RLM subsystem is riddled with `Any` types and missing annotations, contributing to the poor security posture.

## 5. Test Suite Results
- `tests/rlm/`: 43/43 PASS (Happy path only).
- `tests/mcp/test_rlm_config.py`: **FAIL**. Confirming missing Pydantic validation in `McpConfig`.
- `tests/security/test_rlm_traversal_poc.py`: **FAIL (Vulnerability Confirmed)**.
- `tests/security/test_rlm_sandbox_escape_poc.py`: **FAIL (Vulnerability Confirmed)**.

## 6. Behavioral & Edge Testing
- **Operation:** `RLMSession.load_context` / `load_code_context`
- **Scenario:** Arbitrary file read.
- **Result:** Successfully loaded `/etc/passwd`. No path validation against `allowed_roots` or `REPO_ROOT` is performed in the core `RLMSession` class.
- **Operation:** `ProcessSandboxBackend` execution.
- **Scenario:** Executing `os.system()` in "permissive" mode.
- **Result:** **SUCCESSFUL ESCAPE**. The sandbox allows importing `os` and `subprocess` by default. Even "blocked" builtins like `open` can be bypassed via `os.open` or `pathlib`.
- **Operation:** Token Budgeting.
- **Scenario:** Unicode Token Density Attack.
- **Result:** **BYPASS POSSIBLE**. Fixed `chars_per_token=4` undercounts tokens for many languages/scripts, allowing the model to blow past the USD budget before the system notices.

## 7. Documentation & DX Issues
- Stale backup files (`.bak`, `.backup`, `.orig`) cluttering the repo root and `llmc/rlm/`.
- `FIXME` and `TODO` comments regarding missing `RestrictedPython` backends and `litellm` sync calls.

## 8. Most Important Bugs (Prioritized)
1. **[CRITICAL] Arbitrary File Read in RLMSession**: `load_context` and `load_code_context` lack path validation.
2. **[CRITICAL] Sandbox Escape in ProcessSandboxBackend**: Default "permissive" mode is equivalent to no sandbox at all.
3. **[HIGH] Missing Validation in McpConfig**: Tests expect Pydantic `ValidationError` but the class is a standard dataclass with weak manual validation.
4. **[MEDIUM] Budget Bypass**: Inaccurate token estimation via fixed ratio.

## 9. Coverage & Limitations
- Tested core RLM classes and MCP tool wrapper.
- GAP identified: No tests for "Restricted" profile in MCP RLM tool or Denylist enforcement.

## 10. Rem's Vicious Remark
You've built a "Recursive Language Model" that's recursively insecure. Your sandbox is as sturdy as a wet paper bag in a hurricane, and your budget system is basically an "all you can eat" buffet for attackers. I've leaked your secrets and escaped your "isolation" with less effort than it takes to swing my flail. Clean up your garbage files and actually *validate* your inputs, or I'll be back to smash what's left of your "hospital-grade" security!
