# Testing Report - Ruthless Verification

## 1. Scope
- Repo: llmc
- Branch: current (HEAD)
- Date: 2024-12-17
- Feature: Full Repository Audit

## 2. Summary
- **Overall assessment**: Significant issues found. The test suite is brittle, out of sync with implementation, and fails to handle optional dependencies.
- **Key risks**:
    - **Broken CI/CD**: Tests fail due to environmental assumptions and missing dependencies.
    - **False Confidence**: Passing tests may not be testing actual implementation (e.g. MCP tests skipped due to massive failures).
    - **Security Gaps**: Known security gaps (allowlist ignored) are present.
    - **DX**: "Getting Started" experience is broken due to missing dependencies.

## 3. Environment & Setup
- **Initial State**: `pytest` collection failed due to missing `mcp`, `textual` dependencies.
- **Remediation**: Manually installed `mcp`, `textual`, `typer`, `rich`.
- **Finding**: Codebase imports "optional" dependencies (like `llmc_mcp.server` importing `mcp`) at top-level without guards, causing crashes in environments where they are not installed.

## 4. Static Analysis
- **Ruff**: 2797 issues found. High technical debt.
- **Mypy**: 200+ type errors.
- **Black**: 15 files need reformatting.

## 5. Test Suite Results
- **Command**: `pytest --ignore=tests/gap --ignore=tests/mcp --maxfail=1000`
- **Stats**: 11 Failed, 844 Passed, 37 Skipped.
- **Major Failures**:
    - `tests/rag/test_indexer_domain_logic.py`: `AttributeError: module 'llmc.rag.indexer' has no attribute 'get_default_domain'`. API mismatch.
    - `tests/test_indexer_basic.py`: `PermissionError`. Test setup/teardown issue or resource contention.
    - `tests/ruthless/test_mcgrep.py`: CLI commands (`mcgrep`, `llmc-repo-validate`) appear missing or broken.
    - `tests/security/test_pocs.py`: Assertion error in POC injection test.
    - `tests/test_docgen_ruthless_config.py`: Path traversal vulnerability check failed (or passed when it should fail?).

## 6. Behavioral & Edge Testing
- **RAG CLI**:
    - **Status**: FAIL
    - **Issue**: `llmc.rag.cli` fails with `No index database found`. `Transformers/Torch not installed` warnings.
    - **Notes**: CLI does not gracefully handle missing index or guide user to create it.
- **MCP Server**:
    - **Status**: FAIL (Tests)
    - **Issue**: Unit tests (`tests/mcp/test_cmd.py`) test arguments (`allowlist`, `host_mode`) that do not exist in the implementation (`llmc_mcp/tools/cmd.py`).
    - **Notes**: The MCP test suite is effectively describing a different software version.

## 7. Documentation & DX Issues
- `tests/test_model_search_fix.py` is a script masquerading as a test, executing code at import time.
- `AGENTS.md` instructions to install `[rag,dev]` are accurate but the code crashes hard without them, suggesting they shouldn't be optional or code should be more robust.

## 8. Most Important Bugs (Prioritized)

1.  **MCP Test/Impl Mismatch**
    - **Severity**: Critical
    - **Area**: Tests / MCP
    - **Observed**: `tests/mcp/test_cmd.py` calls `validate_command(..., allowlist=...)`.
    - **Expected**: `validate_command` does not accept `allowlist`.
    - **Evidence**: `TypeError: validate_command() got an unexpected keyword argument 'allowlist'`

2.  **Missing Dependencies in Core Imports**
    - **Severity**: High
    - **Area**: Architecture
    - **Observed**: `from llmc_mcp.server import LlmcMcpServer` crashes if `mcp` is missing.
    - **Expected**: Graceful degradation or lazy imports for optional features.
    - **Evidence**: `ImportError: CRITICAL: Missing 'mcp' dependency.`

3.  **RAG Indexer API Regression**
    - **Severity**: High
    - **Area**: RAG
    - **Observed**: `AttributeError: 'get_default_domain'` missing in `indexer.py`.
    - **Evidence**: `tests/rag/test_indexer_domain_logic.py` failure.

## 9. Coverage & Limitations
- **Skipped**: `tests/gap/` (Architectural gaps), `tests/mcp/` (Broken suite).
- **Assumptions**: `pip install -e .` would fix environment, but manual installs were needed.

## 10. Rem's Vicious Remark
The flavor of purple is the taste of a test suite that imports modules which don't exist, tests arguments that were never implemented, and crashes because it can't decide if it wants to be a library or a loose collection of scripts. I found more bugs in your tests than in your code, which is an achievement in itself.
