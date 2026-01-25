# RLM Configuration Surface Implementation Plan

**Project:** LLMC (Large Language Model Compressor)
**Plan Location:** .sisyphus/plans/RLM_Config_Surface_Implementation.md
**Goal:** Make RLM configuration surface TOML-based with hospital-grade validation
**Priority:** P0 (Critical), 1-2 days effort
**Status:** PLANNED

## Context

RLM currently has many hardcoded values spread across multiple modules. This blocks real-world deployments (including hospital environments) because cost limits, timeouts, model selection, and sandbox policy cannot be controlled via configuration.

This implementation will:
- Introduce nested config structures (not purely flat)
- Implement hybrid validation (hard-fail critical; warn+default non-critical)
- Make security policy configurable (default permissive for local dev; restrictive for hospital deployments)
- Enforce config-file-only (no environment variable overrides)
- Follow TDD practices

## Goals

- Implement a robust `load_rlm_config()` that loads `llmc.toml` `[rlm]` settings using LLMC's standard config discovery.
- Externalize all RLM hardcoded values (audit found 92) into `llmc.toml` and/or config defaults.
- Provide a hospital-grade validation story:
  - Critical misconfiguration fails fast with clear errors
  - Non-critical misconfiguration warns and falls back to safe defaults
- Make sandbox policy configurable:
  - Developer-friendly permissive defaults for local use
  - Strict, allowlist-based policy for hospital environments
- Thread config through all RLM components (including `TreeSitterNav`).
- Document the full schema and provide example configs.

## Verification Strategy

**Framework:** pytest

**Key Tests:**
- `tests/rlm/test_config.py`: Nested TOML parsing, hybrid validation, permissive vs restrictive.
- `tests/rlm/test_nav.py`: Config-driven limits.
- `tests/rlm/test_sandbox.py`: Permissive vs restrictive semantics.
- `tests/rlm/test_budget.py`: Pricing validation.

**Minimum Verification Commands:**
- `pytest tests/rlm/test_config.py -v`
- `pytest tests/rlm/test_nav.py -v`
- `pytest tests/rlm/test_sandbox.py -v`
- `pytest tests/rlm/test_budget.py -v`

---

## TODOs

- [x] 1. Baseline Verification & Hardcoded Inventory Audit

  **What to do**:
  - Run existing tests to ensure clean state.
  - Capture a baseline list of candidate literals in `llmc/rlm/` (excluding tests) to make the "92 hardcoded values" target verifiable.
  - Store the list in a scratch artifact (e.g., `.sisyphus/scratch/hardcoded_baseline.txt`) for later comparison.
  - Manual triage: identify which literals are true config knobs vs legitimate constants.

  **Must NOT do**:
  - Do not start modifying code yet.
  - Do not delete the baseline artifact.

  **Parallelizable**: NO (First step)

  **References**:
  - `llmc/rlm/config.py`
  - `llmc/rlm/session.py`
  - `llmc/rlm/nav/treesitter_nav.py`

  **Acceptance Criteria**:
  - `pytest tests/rlm/test_config.py -v` passes.
  - `pytest tests/rlm/test_nav.py -v` passes.
  - Baseline inventory file exists containing output from:
    - `rg -t py '=[^\n]*\b\d+\b' llmc/rlm/ | rg -v '/test_'`
    - `rg -t py '=[^\n]*"[^"]+"' llmc/rlm/ | rg -v '/test_'`


- [x] 2. Implement Config Model & Parsing (TDD)

  **What to do**:
  - Modify `llmc/rlm/config.py` to add nested dataclasses for Budget, Sandbox, LLM, Nav, Session, TokenEstimate, Trace.
  - Implement parsing from dict (using LLMC standard config loading).
  - Implement hybrid validation:
    - Critical errors (negative budget, invalid pricing) -> raise ValueError.
    - Non-critical errors (timeouts out of range) -> log warning + use default.
  - Ensure `tests/rlm/test_config.py::test_negative_budget_raises_valueerror` still passes (hard-fail).

  **Must NOT do**:
  - Do not mutate the input dictionary (avoid `pop()`).
  - Do not invent a new config discovery mechanism; reuse `llmc.core`.

  **Parallelizable**: NO (Blocks other tasks)

  **References**:
  - `llmc/rlm/config.py`
  - `llmc/core.py` (for config discovery)

  **Acceptance Criteria**:
  - New unit tests pass for nested TOML parsing.
  - Regression test passes: parsing does not mutate caller dict.
  - Regression test passes: warn+default paths emit warning (assert via `caplog`).
  - `pytest tests/rlm/test_config.py -v` passes.


- [x] 3. Thread Config Through RLMSession

  **What to do**:
  - Modify `llmc/rlm/session.py`.
  - Replace hardcoded tool limits in `_make_context_search()` with config values.
  - Replace magic numbers for token estimation with config values.
  - Ensure session timeout uses config.

  **Must NOT do**:
  - Do not break existing session behavior if config is missing (defaults should match current behavior).

  **Parallelizable**: YES (After Task 2)

  **References**:
  - `llmc/rlm/session.py`

  **Acceptance Criteria**:
  - Existing tests pass (`pytest tests/rlm/test_session.py` or equivalent).
  - Config values are correctly propagated to session components.


- [x] 4. Thread Config Through TreeSitterNav

  **What to do**:
  - Modify `llmc/rlm/nav/treesitter_nav.py`.
  - Add optional `config` argument to `TreeSitterNav` constructor.
  - Verify callsites via `rg "TreeSitterNav\(" --type py` before modifying.
  - Use config.nav values for: default language, outline depth, read max chars, search max results, preview truncation, token estimation.
  - Update `llmc/rlm/session.py` and `tests/rlm/test_nav.py` to pass config.

  **Must NOT do**:
  - Do not leave hardcoded limits (e.g., `// 4`, `[:200]`).
  - Do not break existing callsites (keep param optional or update all callers).

  **Parallelizable**: YES (After Task 2)

  **References**:
  - `llmc/rlm/nav/treesitter_nav.py`
  - `llmc/rlm/session.py`
  - `tests/rlm/test_nav.py`

  **Acceptance Criteria**:
  - `pytest tests/rlm/test_nav.py -v` passes.
  - `rg "TreeSitterNav\(" --type py` shows no broken callsites.


- [x] 5. Implement Sandbox Permissive/Restrictive Policy

  **What to do**:
  - Modify `llmc/rlm/sandbox/process_backend.py`.
  - Support `security_mode` in config.
  - Implement Permissive mode: allow `allowed_modules = None` (allow all imports), but keep blocked builtins.
  - Implement Restrictive mode: enforce allowlist for imports.

  **Must NOT do**:
  - Do not allow blocked builtins (e.g., `open`, `exec`) in Permissive mode.
  - Do not weaken Hospital deployments (Restrictive must be secure).

  **Parallelizable**: YES (After Task 2)

  **References**:
  - `llmc/rlm/sandbox/process_backend.py`

  **Acceptance Criteria**:
  - Unit tests validate Restrictive mode blocks imports (e.g., `import os` fails).
  - Unit tests validate Permissive mode allows safe imports (e.g., `import os` succeeds).
  - Unit tests validate Blocked Builtins fail in BOTH modes.
  - `pytest tests/rlm/test_sandbox.py -v` passes.


- [x] 6. Budget Pricing Consolidation

  **What to do**:
  - Modify `llmc/rlm/governance/budget.py`.
  - Ensure pricing source of truth is `[rlm.pricing]` from config.
  - Implement hard-fail validation for invalid pricing.

  **Must NOT do**:
  - Do not allow negative prices.
  - Do not allow missing required pricing keys.

  **Parallelizable**: YES (After Task 2)

  **References**:
  - `llmc/rlm/governance/budget.py`

  **Acceptance Criteria**:
  - Unit tests pass for pricing parsing and validation.
  - `pytest tests/rlm/test_budget.py -v` passes.


- [x] 7. Documentation & Final Verification

  **What to do**:
  - Create `DOCS/reference/config/rlm.md` with full schema and examples.
  - Update `DOCS/reference/config/index.md` to link `rlm.md`.
  - Update `docker/deploy/mcp/llmc.toml.example` with complete `[rlm]` example.
  - Create test fixtures: `rlm_config_minimal.toml`, `rlm_config_local_permissive.toml`, `rlm_config_hospital_restrictive.toml`.
  - Add parametrized tests in `tests/rlm/test_config.py` using these fixtures.
  - Perform final audit of hardcoded values against baseline.

  **Must NOT do**:
  - Do not leave undocumented config options.

  **Parallelizable**: NO (Last step)

  **References**:
  - `DOCS/reference/config/rlm.md`
  - `tests/fixtures/`

  **Acceptance Criteria**:
  - Docs created and linked.
  - Fixtures load successfully in tests.
  - `pytest tests/rlm/ -v` passes.
  - No remaining hardcoded behavior-limit literals in `llmc/rlm/` (verify with `rg`).

