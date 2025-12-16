# Testing Report - MCP Hybrid Mode & Repo Consolidation

## 1. Scope
- **Repo:** `llmc`
- **Features:** 
    - Repository Directory Consolidation (HEAD)
    - MCP Hybrid Mode v0.7.0 (feat: 'Trust Issues')
- **Commit:** `70f6258d` (HEAD)
- **Date:** 2025-12-16

## 2. Summary
- **Overall Assessment:** **CAUTIOUS PASS**. The new "Hybrid Mode" feature works as designed and documented. The repository reorganization has caused significant static analysis noise (broken imports/references in un-updated files), but core CLI and MCP server entry points are functional.
- **Key Risks:** 
    - **Security:** "Hybrid Mode" bypasses isolation for `run_cmd`, relying entirely on user trust. If enabled for an untrusted agent, it grants full host RCE.
    - **Stability:** Massive directory moves have likely broken many peripheral scripts and tests that weren't updated. `ruff` reports 444+ errors.

## 3. Environment & Setup
- **OS:** Linux
- **Python:** 3.12 (venv)
- **Dependencies:** `mcp` package required (verified enforcement).

## 4. Static Analysis
- **Tools:** `ruff`, `mypy`
- **Result:** **FAIL (Noise)**
    - **Issues:** ~444 errors.
    - **Cause:** Imports pointing to old locations (`tools.rag...`), `typer` usage in defaults, missing modules.
    - **Impact:** Low for core features (which seem updated), High for peripheral/test code.

## 5. Test Suite Results
- **Gap Tests (Security):**
    - `tests/gap/test_mcp_cmd_policy.py`: **PASS**
    - `tests/gap/test_mcp_cmd_validation.py`: **PASS**
- **New Hybrid Mode Tests:**
    - `tests/gap/security/test_hybrid_mode.py`: **PASS** (Created during session)
        - Verified `run_cmd` bypasses isolation in Hybrid Mode.
        - Verified `run_cmd` enforces isolation in Classic Mode.
        - Verified `execute_code` **ALWAYS** enforces isolation (even in Hybrid Mode).

## 6. Behavioral & Edge Testing

### MCP Hybrid Mode
- **Scenario:** `run_cmd` execution
    - **Hybrid:** Bypasses `require_isolation` -> **PASS**
    - **Classic:** Calls `require_isolation` -> **PASS**
- **Scenario:** `execute_code` execution
    - **Hybrid:** Calls `require_isolation` -> **PASS** (Safe default)
- **Scenario:** Dependency Check
    - **Action:** Run without venv
    - **Result:** `ImportError: CRITICAL: Missing 'mcp' dependency...` -> **PASS**

### CLI Smoke Test
- **Command:** `llmc --help` -> **PASS**
- **Command:** `python -m llmc_mcp.server --help` -> **PASS**

## 7. Documentation & DX Issues
- **Documentation:** `README.md` accurately reflects the new "Binary Trust" security model.
- **DX:** The requirement to run in `.venv` is strictly enforced for MCP, which is good.

## 8. Most Important Bugs / Findings

1.  **Repo Instability (Medium):** The directory consolidation left a trail of broken imports in tests and scripts. `ruff` is screaming. While core works, "development health" is currently low.
2.  **Hybrid Mode RCE (Intended Feature):** `run_cmd` in Hybrid Mode allows `python -c ...` which effectively grants RCE. This is documented as "Trust Issues" but represents a massive hole if turned on accidentally.
    - *Mitigation:* Ensure default is always `classic`. (Checked: Default is `classic` in `McpConfig`).

## 9. Rem's Vicious Remark
I have confirmed that your "Trust Issues" feature indeed trusts the user to not shoot themselves in the foot with a bazooka. `run_cmd` in Hybrid Mode is an open door, while `execute_code` sits behind a locked gate next to it. It's inconsistent, but at least it's documented inconsistent behavior. The repo structure is a battlefield of broken imports—I suggest you sweep up the bodies (fix the lint errors) before the rot sets in.
