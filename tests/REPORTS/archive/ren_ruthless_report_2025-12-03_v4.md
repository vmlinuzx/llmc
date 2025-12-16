# Ruthless Testing Report - Recent Changes
**Date:** 2025-12-03
**Agent:** Ren the Maiden Warrior Bug Hunting Demon
**Target:** Recent commits (Routing Tiers, Docgen Security, Docgen Robustness)

## 1. Scope
- **Routing Tiers:** Validation removal (`llmc.toml`, `config_enrichment.py`)
- **Docgen Security:** Lock file symlink attack (`locks.py`), Path traversal (`gating.py`)
- **Docgen Robustness:** Graph context validation (`graph_context.py`)
- **Docgen CLI UX:** Path handling (`commands/docs.py`)

## 2. Summary
- **Overall Assessment:** The security and robustness fixes are **SOLID**. The routing tier relaxation is **SAFE**.
- **Critical Issues:** None found in the security patches.
- **UX Issues:** **High Severity UX Bug** found in `llmc docs generate`.
- **Regressions:** None detected in existing functionality.

## 3. Test Results

### 3.1 Routing Tiers (PASS)
- **Tests:** `tests/ruthless/test_routing_tiers_ren.py`
- **Findings:**
    - Arbitrary strings ("super-mega-model") accepted: ✅
    - Empty strings accepted: ✅
    - Type conversion (int/float in TOML) works: ✅
    - Validation logic correctly removed: ✅

### 3.2 Docgen Security - Lock Symlink (PASS)
- **Tests:** `tests/ruthless/test_docgen_lock_symlink_ren.py`
- **Findings:**
    - Symlink detection blocks `acquire()`: ✅
    - **CRITICAL:** Target file content PRESERVED (not truncated): ✅
    - Normal file creation works: ✅

### 3.3 Docgen Robustness - Graph Context (PASS)
- **Tests:** `tests/ruthless/test_docgen_graph_crash_ren.py`
- **Findings:**
    - Malformed JSON (list instead of dict) handled gracefully: ✅
    - Invalid field types (entities as list) handled gracefully: ✅
    - Partial corruption (one bad relation) allows valid data to pass: ✅
    - No crashes observed: ✅

### 3.4 Docgen Security - Path Traversal (PASS)
- **Tests:** `tests/ruthless/test_path_traversal_ren.py`
- **Findings:**
    - `../` traversal blocked: ✅
    - Absolute path injection blocked: ✅
    - `resolve_doc_path` correctly enforces `output_dir` boundary: ✅

### 3.5 Docgen CLI UX (FAIL)
- **Tests:** `tests/ruthless/test_cli_ux_bug_ren.py`
- **Findings:**
    - **Scenario:** User runs `llmc docs generate /absolute/path/to/repo/file.py`
    - **Expected:** Generates docs for `file.py`.
    - **Actual:** Crashes with `ValueError: Path traversal detected`.
    - **Cause:** `resolve_doc_path` treats absolute inputs as overrides and fails to relate them to `repo_root` before appending to `output_base`.
    - **Impact:** Annoying UX for users who use tab-completion (which often expands to absolute paths).
    - **Recommendation:** In `llmc/commands/docs.py`, convert input `path` to relative path relative to `repo_root` (if it is inside `repo_root`) before passing to orchestrator.

## 4. Artifacts
- `tests/ruthless/test_routing_tiers_ren.py`
- `tests/ruthless/test_docgen_lock_symlink_ren.py`
- `tests/ruthless/test_docgen_graph_crash_ren.py`
- `tests/ruthless/test_path_traversal_ren.py`
- `tests/ruthless/test_cli_ux_bug_ren.py`

## 5. Ren's Vicious Remark
The security holes are plugged tight enough to choke a goblin. The routing logic is now loose enough to fit a dragon through (as requested).
But who taught you to handle file paths? `llmc docs generate /abs/path` treats your own repo like a hostile alien planet.
Fix the CLI path handling, or I'll start reporting every `File not found` as a critical security incident just to watch you panic.

**Ren out.**
