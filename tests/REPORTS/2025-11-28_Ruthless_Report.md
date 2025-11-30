# Testing Report

## 1. Scope

- **Repo:** `llmc`
- **Feature:** Tool Envelope (TE) & RAG CLI
- **Date:** 2025-11-28
- **Environment:** Linux, Python 3.12.3

## 2. Summary

- **Assessment:** **FUNCTIONAL BUT DIRTY**. The core "passthrough telemetry" requirement is working perfectly. However, the codebase has significant static analysis debt (52 errors) and configuration discrepancies that will bite you later.
- **Key Risks:**
    - **Config/Code Mismatch:** `llmc.toml` implies JSONL telemetry, code enforces SQLite. This will confuse operators.
    - **Partial Implementation:** `cat` and `find` handlers are stubbed or disabled, deviating from SDD v1.2.
    - **Import Hygiene:** Rampant unorganized imports and deprecated typing (pre-3.12 style in a 3.12 project).

## 3. Environment & Setup

- **Runtime:** Python 3.12.3
- **Dependencies:** `textual`, `rich`, `sqlite3` verified.
- **Setup:** Standard `python3` execution works.

## 4. Static Analysis

- **Tool:** `ruff check llmc/te llmc/tui`
- **Result:** **52 Issues**
    - **High Severity:** `subprocess.run` missing `check=...` (potential silent failures).
    - **Medium Severity:** Unused variables (`entry` in `cli.py`), unused imports.
    - **Low Severity:** Deprecated typing (`typing.List` vs `list`), unsorted imports.
- **Notable:** `llmc/te/cli.py:107` assigns `entry` but never uses it.

## 5. Test Suite Results

- **Command:** `pytest tests/test_te_unit.py`
- **Result:** **PASS (34 tests)**
- **Notes:** Tests are green, but they likely test the *logic* of handlers, not the *integration* with the config that disables them. The tests passed even though the feature is "disabled" in production config, suggesting tests use their own mocked config (good for unit tests, bad for catching config drift).

## 6. Behavioral & Edge Testing

### Operation: Telemetry Logging (Passthrough)
- **Scenario:** Run common commands (`ls`, `grep`) with enrichment disabled.
- **Expected:** Commands run, output visible, event logged to DB as 'passthrough'.
- **Actual:** **PASS**.
    - `ls -la` -> Mode: `passthrough`
    - `grep ...` -> Mode: `passthrough` (respects `enabled = false` in toml)
    - `agent_id` correctly captured.
    - DB created at `.llmc/te_telemetry.db`.

### Operation: Enrichment (Manual Force)
- **Scenario:** Manually enable `grep` in a temp config.
- **Expected:** JSON meta header `# TE_BEGIN_META`.
- **Actual:** **PASS**. Enrichment logic works when allowed.
    - **Bug:** The JSON matches count was reported as 0 even when matches existed in the output.

### Operation: RAG CLI
- **Scenario:** `tools.rag.cli search`
- **Expected:** JSON output.
- **Actual:** **PASS**. Returned ranked results.

## 7. Documentation & DX Issues

- **Discrepancy:** SDD v1.2 Section 6 says `te cat` is known. Code `cli.py` says "cat enrichment not yet implemented".
- **Discrepancy:** SDD Section 5 & `config.py` default to `te_telemetry.jsonl`. Code `telemetry.py` hardcodes `te_telemetry.db`.

## 8. Most Important Bugs (Prioritized)

1.  **Telemetry Path Hardcoded (Medium)**
    - **Area:** `llmc/te/telemetry.py`
    - **Issue:** Ignores `llmc.toml` config for telemetry path. Enforces `.db`.
    - **Risk:** User configures a path, TE ignores it, data goes elsewhere.

2.  **Grep Match Count Zero (Low)**
    - **Area:** `llmc/te/handlers/grep.py`
    - **Issue:** In manual testing, `grep` found matches but JSON metadata reported `"matches": 0`.
    - **Risk:** misleading analytics.

3.  **Unchecked Subprocess (Medium)**
    - **Area:** `llmc/te/cli.py`, `llmc/te/handlers/grep.py`
    - **Issue:** `subprocess.run` without `check=True` or `check=False`.
    - **Risk:** Silent failures if underlying tools crash.

## 9. Conclusion

The system is dogfood-ready for **telemetry gathering**. The "disabled by default" enrichment strategy is effective. The TUI (TBD) should read from `.llmc/te_telemetry.db`.

**Recommendation:** Fix the telemetry path discrepancy before shipping to avoid confused users looking for a JSONL file that doesn't exist.
