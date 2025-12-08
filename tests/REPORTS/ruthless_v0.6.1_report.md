# Testing Report - Ruthless Validation of v0.6.1 Features

## 1. Scope
- **Repo:** `~/src/llmc`
- **Features:** `mcgrep` (Semantic Search CLI), `llmc repo validate` (Repo Validator)
- **Commit:** `39cf959` (Merge remote README changes)
- **Date:** 2025-12-07

## 2. Summary
- **Overall Assessment:** **PASS with Minor Issues**. The new features are functional and robust against common failures.
- **Key Risks:** 
  - `llmc repo validate` allows `file://` URLs, potentially allowing local filesystem probing (low risk due to path suffixing).
  - `mcgrep` test suite is brittle regarding environment (`PYTHONPATH`).
  - `repo_validator` requires a `[routing]` section which might trip up users upgrading from older configs.

## 3. Environment & Setup
- **Setup:** `export PYTHONPATH=$PYTHONPATH:.` required to run tests.
- **Dependencies:** `typer`, `pytest` confirmed installed.
- **Workarounds:** Had to explicitly set `PYTHONPATH` for subprocess tests to find the `llmc` package.

## 4. Static Analysis
- **Linting:** Not run (out of scope for this session, focused on dynamic testing).
- **Structure:** `llmc/mcgrep.py` and `llmc/commands/repo_validator.py` follow project conventions.

## 5. Test Suite Results
- **Existing Tests:**
  - `tests/ruthless/test_mcgrep.py`: **PASS** (after env fix).
  - `tests/ruthless/test_repo_validator.py`: **PASS** (after env fix).
- **New Ruthless Tests (`test_rem_attack.py`):**
  - **BOM Detection:** **PASS**. Correctly identifies files with UTF-8 BOM.
  - **Connectivity SSRF:** **PASS**. `file://` URIs are attempted but fail safely due to path suffixing (`/api/tags`).
  - **Config Validation:** **PASS**. Correctly identifies missing sections (including `[routing]`).
  - **Large Inputs:** **PASS**. `mcgrep` truncates long lines and summaries.

## 6. Behavioral & Edge Testing

### mcgrep
- **Scenario:** Search with no index.
  - **Behavior:** correctly reports "No index found" and suggests `mcgrep watch`.
- **Scenario:** Search with malformed queries.
  - **Behavior:** Handles them as string literals.
- **Scenario:** Long output.
  - **Behavior:** Truncated to avoid flooding console.

### repo_validator
- **Scenario:** Missing `[routing]` section.
  - **Behavior:** Warns "No [routing.slice_type_to_route] defined".
  - **Note:** This is stricter than previous versions but ensures correctness.
- **Scenario:** `file://` URL in config.
  - **Behavior:** Tries to access `file://.../api/tags`, fails with `Not a directory` or `FileNotFound`.
  - **Risk:** Minimal. Logic appends `/api/tags`, preventing arbitrary file reads (unless an attacker controls the filesystem structure to match).

## 7. Documentation & DX Issues
- **DX:** `mcgrep` subprocess tests fail by default if `llmc` is not installed in site-packages. Devs running `pytest` locally might face this.
- **Docs:** The warning for missing `[routing]` suggests it's mandatory now. Ensure `README` or migration guide reflects this.

## 8. Most Important Bugs / Findings

1.  **Title:** Validator allows `file://` URLs in connectivity checks
    *   **Severity:** Low / Informational
    *   **Area:** Security
    *   **Description:** `check_ollama_connectivity` uses `urllib.request.urlopen` which supports `file://`.
    *   **Mitigation:** `url` has `/api/tags` appended, preventing simple arbitrary file read.
    *   **Recommendation:** Whitelist `http` and `https` schemes in `check_ollama_connectivity`.

2.  **Title:** `mcgrep` test suite environment dependency
    *   **Severity:** Low / DX
    *   **Area:** Tests
    *   **Description:** `subprocess.run` in tests inherits strict environment, failing to find `llmc` package if not installed editable.
    *   **Fix:** Add `PYTHONPATH` to `subprocess.run` env or use `tox`/`nox`.

## 9. Coverage & Limitations
- Tested on Linux.
- Did not test Windows-specific path issues.
- Did not test actual RAG retrieval quality (mocked).

## 10. Rem's Vicious Remark
I have flailed the code until it confessed its secrets. The validator is a bit of a voyeur with that `file://` access, peeping where it shouldn't, but at least it's wearing blinders (`/api/tags`). The search tool `mcgrep` stands strong, though its tests are as fragile as a goblin's ego without their precious `PYTHONPATH`. 

Fix the URL validation, or I shall return with a larger flail.
