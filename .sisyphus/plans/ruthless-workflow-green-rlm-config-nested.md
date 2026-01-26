# Ruthless Workflow Green (feat/rlm-config-nested-phase-1x)

## Context

### Original Request
Look at the recent testing reports and build a plan to resolve.

### Baseline / Target
- **Branch baseline**: `feat/rlm-config-nested-phase-1x` (referenced by the 2026-01-25 reports)
- **Target gate**: make the **Ruthless Testing Workflow** green (as defined in `.agent/workflows/ruthless-testing.md`).

### Primary Evidence (Reports + Logs)
Most recent artifacts are in `tests/REPORTS/current/`:
- `tests/REPORTS/current/rem_testing_2026-01-25.md` - security + RLM risk summary, ruff/mypy counts
- `tests/REPORTS/current/feat_rlm_config_nested_phase_1x_test_report.md` - RLM MCP/tool issues and repro pointers
- `tests/REPORTS/current/full_run.log` - shows a pytest collection error (missing `respx`)
- `tests/REPORTS/current/rlm_config_test_run.log` - shows `tests/mcp/test_rlm_config.py` failures
- `tests/REPORTS/current/pytest_rag_router.txt` + `tests/REPORTS/current/pytest_rag_router_fixed*.txt` - indicates a historical router failure and subsequent fixes

Related workflow + docs:
- `.agent/workflows/ruthless-testing.md` - “CI-like” verification flow
- `DOCS/development/testing.md` - test suite guidance (notes `tests/gap/` expectations)
- `Makefile` - local `make test` (ruff + mypy script + pytest)

### Key Issues Surfaced

**A) Pytest collection error (blocks the suite)**
- `tests/REPORTS/current/full_run.log` shows:
  - `tests/agent/test_openai_compat_backend.py` fails collection: `ModuleNotFoundError: No module named 'respx'`

**B) MCP config validation mismatch**
- `tests/mcp/test_rlm_config.py` expects `pydantic.ValidationError` for invalid inputs (wrong types / unexpected dict nesting).
- `llmc_mcp/config.py` uses dataclasses + manual `.validate()` methods (no Pydantic; no automatic type validation in `__init__`).

**C) RLM MCP tool path validation crash**
- `llmc_mcp/tools/rlm.py` calls `validate_path(..., allowed_roots=..., repo_root=..., operation=...)`
- `llmc_mcp/tools/fs.py:validate_path` signature is currently `validate_path(path, allowed_roots)` → mismatch causes runtime `TypeError`.
- Repro exists: `tests/REPRO_rlm_path_explosion.py` (not auto-collected by pytest, but demonstrates the bug).

**D) Security posture concerns (not necessarily “pytest failing”, but a red flag)**
- `llmc/rlm/config.py` defaults `security_mode = "permissive"`.
- `llmc/rlm/session.py` reads arbitrary filesystem paths when passed a `Path` (no allowlist enforcement).
- `tests/security/test_rlm_traversal_poc.py` and `tests/security/test_rlm_sandbox_escape_poc.py` are written as POCs that *confirm* vulnerabilities.
  - If the goal is “hospital-grade security”, these should be converted into regression tests (or moved out of the default suite) after fixes land.

---

## Work Objectives

### Core Objective
On `feat/rlm-config-nested-phase-1x`, bring the repo back to a state where the “ruthless” verification flow can run end-to-end without errors, and where the RLM/MCP integration does not crash on supported inputs.

### Concrete Deliverables
- A reproducible, ordered set of fixes that eliminates:
  - pytest collection errors
  - MCP config validation test failures
  - MCP RLM tool runtime signature mismatch
- A security hardening path for RLM that aligns defaults + tests with “secure by default” (no silent host escape).
- Verification evidence captured in `.sisyphus/evidence/` for each major step.

### Definition of Done (DoD)
- [ ] The ruthless flow in `.agent/workflows/ruthless-testing.md` can be executed end-to-end with:
  - [ ] `ruff check .` → exit code 0
  - [ ] `mypy llmc/ --ignore-missing-imports` → exit code 0 (or documented/approved scoped alternative)
  - [ ] `python3 -m pytest tests/ -v --maxfail=10 --tb=short` → exit code 0
  - [ ] Behavioral smoke commands in the workflow return exit code 0

### Guardrails (Must / Must Not)
- Must fix root causes (no “mock away” real bugs).
- Must not disable or skip tests to achieve green.
- Must not water down security by reclassifying vulnerabilities as “expected”.
- Must keep changes focused on making this branch healthy; avoid unrelated refactors.

---

## Verification Strategy

### Test Infrastructure
- **Exists**: YES (pytest configured in `pyproject.toml`)
- **Workflow**: `.agent/workflows/ruthless-testing.md`
- **Note**: `tests/_plugins/pytest_ruthless.py` imposes constraints (e.g., sleep/network).

### Evidence Capture Convention
For each major task, capture the raw output in `.sisyphus/evidence/`:
- `task-01-baseline-ruff.txt`
- `task-01-baseline-mypy.txt`
- `task-01-baseline-pytest.txt`
- etc.

---

## Task Flow

High-level dependency chain:

1) Reproduce + baseline → 2) unblock collection (`respx`) → 3) MCP config validation → 4) MCP RLM validate_path signature → 5) RLM security hardening → 6) ruff/mypy cleanup → 7) final ruthless run

---

## TODOs

### 0. Baseline the Current Failures (no fixes yet)

**What to do**:
- Ensure branch is checked out: `feat/rlm-config-nested-phase-1x`.
- Run the ruthless workflow commands (or the closest equivalent) and capture outputs:
  - `ruff check .`
  - `mypy llmc/ --ignore-missing-imports`
  - `python3 -m pytest tests/ -v --maxfail=10 --tb=short`
- Identify exact current blockers (collection errors, top failing suites, top ruff/mypy errors).

**Parallelizable**: NO (establishes ground truth)

**References**:
- `.agent/workflows/ruthless-testing.md` - defines what “green” means operationally
- `tests/REPORTS/current/full_run.log` - known collection error for `respx`

**Acceptance Criteria**:
- [x] Evidence files created in `.sisyphus/evidence/` with the outputs above
- [x] A short list of current top blockers (ranked) recorded in the PR description or report

---

### 1. Fix Pytest Collection: Add or Replace `respx`

**What to do**:
- Decide the minimal-change resolution:
  - Preferred: add `respx` as a dev/test dependency, since `tests/agent/test_openai_compat_backend.py` uses it.
  - Alternative: refactor the test to use an existing HTTPX mocking tool already in the stack (only if repo policy rejects new deps).
- Ensure the dependency is installed by the workflow’s recommended install command:
  - `pip install -e ".[dev,rag,tui,agent]"`

**Parallelizable**: YES (can run alongside Task 2 planning), but implementation should land first because it unblocks pytest collection.

**References**:
- `tests/REPORTS/current/full_run.log` - shows `ModuleNotFoundError: respx`
- `tests/agent/test_openai_compat_backend.py` - imports and usage of `respx`
- `pyproject.toml` - where `project.optional-dependencies.dev` and/or `agent` live

**Acceptance Criteria**:
- [x] `python3 -m pytest tests/agent/test_openai_compat_backend.py -v` → PASS
- [x] `python3 -m pytest tests/ -v --maxfail=10 --tb=short` → no longer stops at collection due to `respx`

---

### 2. Make MCP Config Validation Consistent (dataclasses vs Pydantic)

**What to do**:
- Align `tests/mcp/test_rlm_config.py` expectations with how `llmc_mcp/config.py` is actually designed.
- Recommended direction (least invasive): keep dataclasses, but enforce validation deterministically:
  - Add `__post_init__` on `McpConfig` / `McpRlmConfig` to type-check nested fields and call `.validate()`.
  - Ensure wrong-typed configs (e.g., `rlm` passed as a dict) raise a deterministic exception (likely `ValueError`).
  - Update tests to assert the correct exception type and message.

**Must NOT do**:
- Don’t silently accept dicts that later cause attribute errors.
- Don’t introduce Pydantic conversion unless there’s a broader repo mandate.

**Parallelizable**: YES (with Task 3)

**References**:
- `tests/mcp/test_rlm_config.py` - current expected behavior
- `llmc_mcp/config.py` - actual config model implementation

**Acceptance Criteria**:
- [x] `python3 -m pytest tests/mcp/test_rlm_config.py -v` → PASS
- [x] `McpConfig()` defaults still match the test expectations
- [x] Invalid configurations fail early with a clear error

---

### 3. Fix MCP RLM Tool Crash: `validate_path` Signature Alignment

**What to do**:
- Resolve the mismatch between:
  - `llmc_mcp/tools/rlm.py` calling `validate_path(..., allowed_roots=..., repo_root=..., operation=...)`
  - `llmc_mcp/tools/fs.py:validate_path(path, allowed_roots)`
- Recommended direction:
  - Extend `validate_path` to accept optional keyword args (`repo_root`, `operation`) without breaking existing call sites.
  - Use `repo_root` to resolve relative `allowed_roots` consistently (security + correctness).
  - Keep backward compatibility: existing calls `validate_path(path, allowed_roots)` must continue to work.

**Parallelizable**: YES (with Task 2)

**References**:
- `llmc_mcp/tools/fs.py` - current `validate_path` implementation and tests
- `llmc_mcp/tools/rlm.py` - current `validate_path` call site
- `tests/mcp/test_fs.py` - path validation test patterns
- `tests/REPRO_rlm_path_explosion.py` - repro (manual run) demonstrating the current mismatch

**Acceptance Criteria**:
- [x] `python3 -m pytest tests/mcp/test_fs.py -v` → PASS
- [x] `python3 -m pytest tests/mcp/test_tool_rlm.py -v` → PASS
- [x] Manual repro: `python3 -m pytest tests/REPRO_rlm_path_explosion.py -v -s` no longer prints a signature mismatch (if the intent is to fix the crash)

---

### 4. RLM Security Hardening: Make Defaults “Safe by Default”

**What to do**:
- Change RLM execution to be safe by default for typical users:
  - Default `RLMConfig.security_mode` should be restrictive/secure.
  - `RLMSession.load_context(Path)` and `load_code_context(Path)` must not allow arbitrary filesystem reads by default.
  - MCP tool path loading must remain allowlisted via `allowed_roots` and denylist globs.
- Address the security POC situation:
  - Convert POC tests into regression tests that assert blocking behavior, OR
  - Move POC-style “confirm vulnerability” tests out of the default suite (e.g., to `tests/security/exploits/`) and keep regression tests in `tests/security/`.

**Parallelizable**: NO (touches core behavior; do after functional blockers are removed)

**References**:
- `llmc/rlm/config.py` - currently defaults `security_mode="permissive"`
- `llmc/rlm/session.py` - reads `Path` directly in `load_context`
- `llmc/rlm/sandbox/process_backend.py` - enforcement of security_mode
- `tests/security/test_rlm_traversal_poc.py` - current POC behavior
- `tests/security/test_rlm_sandbox_escape_poc.py` - current POC behavior
- `tests/security/README.md` - intended structure: POCs vs regression tests

**Acceptance Criteria**:
- [x] `python3 -m pytest tests/security/ -v` → PASS
- [x] A default-config RLM session cannot import `os` / execute host commands in “normal” mode
- [x] A default-config RLM session cannot read `/etc/passwd` by passing a `Path`

---

### 5. Static Analysis: Make `ruff check .` Green

**What to do**:
- Run `ruff check .` and fix violations until exit code is 0.
- Prioritize rules that indicate real bugs or poor error handling (examples seen in reports: `B904`, `E722`, `F841`).
- Prefer small mechanical fixes over broad refactors.

**Parallelizable**: YES (can run while security hardening is in progress, but expect conflicts)

**References**:
- `tests/REPORTS/current/ruff_report.txt` - example ruff output from this branch’s testing
- `pyproject.toml:[tool.ruff]` - ruff config and ignore rules
- `Makefile:test` - local gate includes `ruff check .`

**Acceptance Criteria**:
- [~] `ruff check .` → exit code 0

---

### 6. Static Analysis: Make `mypy llmc/ --ignore-missing-imports` Green

**What to do**:
- Run `mypy llmc/ --ignore-missing-imports` and fix errors until exit code is 0.
- Start with the RLM/MCP modules implicated by the reports, then expand outward.
- Use focused typing fixes:
  - add missing annotations
  - tighten return types
  - use `cast()` / `TypedDict` where appropriate
  - use narrowly-scoped `# type: ignore[code]` only when unavoidable

**Parallelizable**: PARTIALLY (best done after major refactors stop moving signatures)

**References**:
- `tests/REPORTS/current/mypy_report.txt` - example mypy output
- `pyproject.toml:[tool.mypy]` - mypy configuration

**Acceptance Criteria**:
- [~] `mypy llmc/ --ignore-missing-imports` → exit code 0

---

### 7. Final Ruthless Run + Evidence

**What to do**:
- Re-run the complete ruthless flow (static analysis + pytest + behavioral checks).
- Save outputs to `.sisyphus/evidence/` and summarize what changed compared to baseline.

**Parallelizable**: NO

**References**:
- `.agent/workflows/ruthless-testing.md`

**Acceptance Criteria**:
- [ ] All commands in the ruthless flow return exit code 0
- [ ] Evidence outputs captured and linked

---

## Notes / Defaults Applied

- Default assumption: adding `respx` as a dev/test dependency is acceptable because it is required for an existing test file (`tests/agent/test_openai_compat_backend.py`).
- Default assumption: security posture should be improved (safe-by-default) rather than treating POC-confirmed vulnerabilities as “expected”.
