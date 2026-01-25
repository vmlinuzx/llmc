# RLM Configuration Surface (Phase 1.X)

## Context

### Original Request
Refactor the current flat RLM configuration into a deeply nested configuration system (Phase 1.X, P0) so that ~80+ currently hardcoded/defaulted values become configurable via `llmc.toml`, with sensible defaults and safe migration.

### Evidence (Repo)
- Roadmap requirement: `DOCS/ROADMAP.md` (Phase `1.X RLM Configuration Surface Implementation (P0)`) describes the target nested TOML shape and calls out "80+ hardcoded values".
- Current config is flat and only partially parses nested sections:
  - `llmc/rlm/config.py` defines `RLMConfig` and `load_rlm_config()`.
  - It only handles `[rlm]` flat keys + partial `[rlm.sandbox]` (only `blocked_builtins` and `allowed_modules`).
  - Nested tables like `[rlm.budget]` are currently ignored.
- Existing RLM config test coverage:
  - `tests/rlm/test_config.py` asserts defaulting, partial merges, sandbox overrides (partial), unknown key ignoring, and type-mismatch behavior.
  - TOML fixtures exist but are not yet referenced by tests: `tests/fixtures/rlm_config_minimal.toml`, `tests/fixtures/rlm_config_permissive.toml`, `tests/fixtures/rlm_config_restrictive.toml`.
- Related modules already depending on config values:
  - `llmc/rlm/session.py` reads many config fields and also contains additional hardcoded constants.
  - `llmc/rlm/governance/budget.py` already has `BudgetConfig` and `load_pricing()` reading `[rlm.pricing]`.
  - `llmc/commands/rlm.py` currently uses `RLMConfig()` defaults and applies CLI overrides without loading `llmc.toml`.

### Decisions (Confirmed)
- Canonical config file: `llmc.toml` with nested `[rlm.*]` sections.
- Migration/back-compat policy: support legacy flat keys; nested wins when both are set; emit deprecation warnings.
- No environment-variable overrides in Phase 1.X.
- Pricing config (Phase 1.X): keep canonical pricing at `[rlm.pricing]` (defer `[rlm.budget.pricing]` migration).
- Tests: YES, use pytest with TDD.

### Metis Review (Key Guardrails Incorporated)
- Establish a baseline test run before refactor (capture output).
- Build an explicit key inventory (what becomes configurable, where it lives in TOML).
- Reconcile that `BudgetConfig` already exists in `llmc/rlm/governance/budget.py` (avoid duplicate class names).
- Account for direct `RLMConfig(...)` instantiations across tests and CLI.
- Update/add tests and fixtures early; avoid a "big bang" refactor.

---

## Work Objectives

### Core Objective
Implement Phase 1.X nested config surface for RLM so that:
1) nested TOML sections under `[rlm.*]` are actually parsed and validated
2) legacy flat keys remain supported with warnings
3) the RLM implementation uses config values instead of hardcoded constants

### Concrete Deliverables
- Nested config parsing for the following sections in `llmc.toml`:
  - `[rlm]` (model selection)
  - `[rlm.budget]`
  - `[rlm.sandbox]`
  - `[rlm.llm.root]` / `[rlm.llm.sub]`
  - `[rlm.session]`
  - `[rlm.trace]`
  - `[rlm.token_estimate]`
  - Pricing remains `[rlm.pricing]` (existing behavior)
- Nested config *structures* available to code via `RLMConfig` (see SDD Appendix).
- Wiring updates so major RLM subsystems pull from config (budget, sandbox, llm params, token estimation, trace/preview limits, and other literals).
- Updated/new pytest coverage for nested parsing + precedence + warnings.
- Documentation: `DOCS/reference/rlm-config.md` including migration notes.

### Definition of Done
- `pytest tests/rlm/test_config.py -v` passes (and new tests for nested behavior pass).
- `pytest tests/rlm -q` passes.
- `load_rlm_config()` correctly reads `llmc.toml` defaults + nested overrides.
- When both legacy + nested keys exist, nested wins and a deprecation warning is emitted.
- No env-var overrides added.
- Pricing remains read from `[rlm.pricing]` only.
- Docs for the nested schema exist and include at least 2 concrete examples.

### Must Have
- Preserve current default behavior when config is missing.
- Support the existing fixture TOMLs (including alias handling where fixtures differ from canonical names).
- Provide actionable deprecation warnings.

### Must NOT Have (Guardrails)
- No new environment-variable overrides for RLM.
- Do not move pricing into `[rlm.budget.pricing]` in Phase 1.X (defer).
- Do not change default behavior (values) unless explicitly required for correctness.
- Avoid unrelated refactors outside RLM config + wiring targets listed in this plan.

---

## Verification Strategy

### Test Decision
- Infrastructure exists: YES (pytest configured in `pyproject.toml`).
- User wants tests: YES (TDD).

### Test Commands (Primary)
- Focused: `pytest tests/rlm/test_config.py -v`
- Full RLM: `pytest tests/rlm -q`

### Manual Verification (Always)
- Run the CLI with a sample `llmc.toml` and ensure overrides take effect:
  - `llmc rlm query "..." --file <path>` (verify printed model/budget reflect config)

---

## Task Flow

0. Baseline snapshot (tests)
1. Key inventory + schema mapping (SDD appendix validation)
2. RED: add nested-config tests (fails against current loader)
3. GREEN: implement nested parsing + warnings in `llmc/rlm/config.py`
4. REFACTOR: add nested config views + validation
5. Wire config through RLM modules + CLI
6. Docs + examples
7. Final verification

---

## TODOs

- [x] 0. Capture baseline behavior

  What to do:
  - Run `pytest tests/rlm/test_config.py -v` and capture exact output.
  - Record output to a scratch evidence file (suggested): `.sisyphus/evidence/rlm-config-baseline.txt`.

  Must NOT do:
  - Do not change any code before capturing baseline output.

  Parallelizable: NO

  References:
  - `tests/rlm/test_config.py` - baseline expectations for loader behavior
  - `pyproject.toml` - pytest configuration and defaults

  Acceptance Criteria:
  - Baseline output captured and includes the pass count.

- [x] 1. Build the config key inventory ("80+ values" mapping)

  What to do:
  - Enumerate all current config/default surfaces for RLM by scanning:
    - `llmc/rlm/config.py` (`RLMConfig` defaults)
    - `llmc/rlm/session.py` (hardcoded literals and defaults)
    - `llmc/rlm/prompts.py`, `llmc/rlm/nav/treesitter_nav.py`, `llmc/rlm/sandbox/*` (hardcoded limits/messages)
  - Produce a single mapping table (append/update in the SDD Appendix section of this plan) with:
    - Value name
    - Current location
    - Canonical TOML path (nested)
    - Legacy TOML alias path (if any)
    - Default value
    - Notes (warning, type/range constraints)

  Must NOT do:
  - Do not change runtime behavior; this task is inventory/spec only.

  Parallelizable: YES (with 2)

  References:
  - `llmc/rlm/config.py` - existing defaults (many count toward the "80+")
  - `llmc/rlm/session.py` - additional literals to externalize
  - `DOCS/ROADMAP.md` - target nested schema guidance

  Acceptance Criteria:
  - Mapping table exists and covers (at minimum) every field in `RLMConfig` plus the main literals in `session.py`.

- [x] 2. RED: Add pytest coverage for nested parsing + precedence + warnings

  What to do:
  - Extend/add tests (likely in `tests/rlm/test_config.py`) to cover:
    - `[rlm.budget]` parsing (e.g., max_session_budget_usd)
    - Alias support for `max_tokens_per_session` -> canonical `max_session_tokens` (warn)
    - `[rlm.sandbox]` parsing for ALL sandbox keys (backend, security_mode, timeouts, max_output_chars)
    - `[rlm.llm.root]` and `[rlm.llm.sub]` parsing for temperature/max_tokens
    - Precedence rule: when both legacy flat key and nested key set, nested wins and warns
    - Warning mechanism uses `DeprecationWarning` and is de-duped per key
  - Add tests that load the fixture TOMLs:
    - `tests/fixtures/rlm_config_minimal.toml`
    - `tests/fixtures/rlm_config_permissive.toml`
    - `tests/fixtures/rlm_config_restrictive.toml`

  Must NOT do:
  - Do not weaken existing tests; preserve current behavior assertions where still applicable.

  Parallelizable: YES (with 1)

  References:
  - `tests/rlm/test_config.py` - existing test patterns to follow
  - `tests/fixtures/rlm_config_*.toml` - representative nested config inputs

  Acceptance Criteria:
  - New tests fail against the current implementation (at least one failing assertion demonstrating missing nested parsing).

- [x] 3. GREEN: Implement nested parsing + deprecation warnings in `llmc/rlm/config.py`

  What to do:
  - Implement parsing for nested tables under `[rlm.*]` with the precedence policy:
    - If nested value present: use it
    - Else if legacy flat value present: use it + emit `DeprecationWarning`
    - If both present: nested wins + emit `DeprecationWarning`
  - Preserve "unknown keys ignored" behavior (tests expect this).
  - Ensure type/range errors are surfaced similarly to today (TypeError/ValueError).
  - Ensure `[rlm.budget]` values actually impact budget fields.
  - Ensure `[rlm.sandbox]` keys (not just lists) actually override.

  Must NOT do:
  - Do not add env-var overrides.
  - Do not change pricing location (keep `[rlm.pricing]` handled by `budget.py:load_pricing()`).

  Parallelizable: NO (depends on 2)

  References:
  - `llmc/rlm/config.py` - implement nested parsing here
  - `llmc/core.py` - `load_config()` contract (reads `llmc.toml`)
  - `llmc/te/config.py` - nested TOML parsing precedent
  - `tests/rlm/test_config.py` - required behavior

  Acceptance Criteria:
  - `pytest tests/rlm/test_config.py -v` passes.
  - New nested parsing tests from task 2 pass.

- [x] 4. Add nested config structures (views) and wire them through constructors

  What to do:
  - Provide nested config structures accessible from `RLMConfig`:
    - `config.budget` should reuse `llmc/rlm/governance/budget.py:BudgetConfig`
    - `config.sandbox` should provide a sandbox config view used by `create_sandbox(...)`
    - `config.llm` should provide root/sub model parameter views
    - `config.trace`, `config.session`, `config.token_estimate`, and (optionally) `config.nav`, `config.prompts`
  - Update wiring to use these nested views where it reduces mismatch:
    - `llmc/rlm/session.py`: use `config.budget` and `config.sandbox` to initialize `TokenBudget` and sandbox
    - Ensure any remaining hardcoded literals in RLM critical path are moved to config (per inventory)

  Must NOT do:
  - Avoid broad signature churn across modules unless required.

  Parallelizable: NO (depends on 3)

  References:
  - `llmc/rlm/session.py` - currently constructs `BudgetConfig` manually and passes sandbox params
  - `llmc/rlm/sandbox/interface.py:create_sandbox` - consumes sandbox params
  - `llmc/rlm/governance/budget.py:BudgetConfig` - reuse as nested budget view

  Acceptance Criteria:
  - `pytest tests/rlm -q` passes.
  - Budget and sandbox initialization paths use nested config views (no manual remapping that risks drift).

- [x] 5. Wire config into prompts/nav/trace and eliminate remaining hardcoded values

  What to do:
  - Move remaining hardcoded constants (identified in task 1 inventory) into appropriate `[rlm.*]` config sections.
  - At minimum, ensure the defaults in code match the config defaults exactly.
  - Update:
    - `llmc/rlm/prompts.py` (prompt text pieces / templates)
    - `llmc/rlm/nav/treesitter_nav.py` (chunk sizes, preview sizes, search limits)
    - `llmc/rlm/session.py` trace preview and tool feedback strings/limits
    - `llmc/rlm/sandbox/process_backend.py` defaults already exist; ensure `create_sandbox` receives config values

  Must NOT do:
  - Avoid introducing new functionality; this is surfacing existing knobs.

  Parallelizable: YES (some subparts)

  References:
  - `llmc/rlm/prompts.py` - prompt template hardcoded strings
  - `llmc/rlm/nav/treesitter_nav.py` - read/search defaults
  - `llmc/rlm/session.py` - many remaining literal values
  - `DOCS/ROADMAP.md` - lists prompt formatting and preview limits as part of the 80+

  Acceptance Criteria:
  - Inventory table items are all either (a) moved to config and wired, or (b) explicitly documented as deferred.
  - `pytest tests/rlm -q` passes.

- [x] 6. Update CLI command to load config by default

  What to do:
  - Update `llmc/commands/rlm.py` to call `load_rlm_config()` (from `llmc/rlm/config.py`) instead of starting from `RLMConfig()` defaults.
  - Apply CLI overrides after loading config (model, budget, trace).

  Must NOT do:
  - Do not add env overrides.

  Parallelizable: YES (with 5)

  References:
  - `llmc/commands/rlm.py` - current CLI behavior and override points
  - `llmc/rlm/session.py` - uses config for runtime

  Acceptance Criteria:
  - Manual run confirms config values are reflected in CLI output (model/budget/trace).
  - RLM tests still pass.

- [x] 7. Documentation: RLM config reference + migration notes

  What to do:
  - Create `DOCS/reference/rlm-config.md` documenting:
    - Nested schema under `[rlm.*]`
    - Defaults and types
    - Examples (dev permissive + restrictive)
    - Migration notes (legacy flat keys, warning behavior)
    - Pricing note: Phase 1.X keeps `[rlm.pricing]` canonical

  Must NOT do:
  - Avoid large doc rewrites outside the specific RLM config reference.

  Parallelizable: YES (after 3)

  References:
  - `DOCS/ROADMAP.md` - acceptance criteria includes a full config reference doc
  - `tests/fixtures/rlm_config_*.toml` - example configs to document

  Acceptance Criteria:
  - `DOCS/reference/rlm-config.md` exists and includes at least 2 end-to-end config examples.

- [x] 8. Final verification

  What to do:
  - Run:
    - `pytest tests/rlm/test_config.py -v`
    - `pytest tests/rlm -q`
  - Confirm deprecation warnings appear for legacy keys and do not spam.

  Parallelizable: NO

  Acceptance Criteria:
  - All tests pass.
  - Defaults preserved (compare against task 0 baseline where applicable).

---

## SDD Appendix (Embedded)

### A. Canonical TOML Schema (Phase 1.X)

Note: pricing stays under `[rlm.pricing]` in Phase 1.X (defer `[rlm.budget.pricing]`).

```toml
[rlm]
root_model = "ollama_chat/qwen3-next-80b"
sub_model = "ollama_chat/qwen3-next-80b"

[rlm.budget]
max_session_budget_usd = 1.00
max_session_tokens = 500_000
soft_limit_percentage = 0.80
max_subcall_depth = 5

[rlm.pricing]
default = { input = 0.01, output = 0.03 }
"ollama_chat/qwen3-next-80b" = { input = 0.0, output = 0.0 }

[rlm.sandbox]
backend = "process"
security_mode = "permissive"
code_timeout_seconds = 30
max_output_chars = 10_000
blocked_builtins = ["open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "exit", "quit"]
allowed_modules = ["json", "re", "math", "collections", "itertools", "functools", "operator", "string", "textwrap", "datetime", "copy", "typing", "dataclasses"]

[rlm.llm.root]
temperature = 0.1
max_tokens = 4096

[rlm.llm.sub]
temperature = 0.1
max_tokens = 1024

[rlm.token_estimate]
chars_per_token = 4
safety_multiplier = 1.2

[rlm.session]
max_turns = 20
session_timeout_seconds = 300
max_context_chars = 1_000_000

[rlm.trace]
enabled = true
prompt_preview_chars = 200
response_preview_chars = 200
match_preview_chars = 200
stdout_preview_chars = 2000
```

### B. Precedence & Deprecation Policy
- Canonical values live under nested sections.
- Legacy flat keys (e.g., `[rlm].max_session_budget_usd`) remain supported in Phase 1.X.
- If both legacy + canonical exist for the same semantic value: canonical wins.
- Emit `DeprecationWarning` via `warnings.warn(..., stacklevel=2)` for:
  - any legacy key used
  - any legacy-vs-canonical conflict
- Prefer de-duping warnings per key per load.

### C. Implementation Approach (Why "nested views")
To minimize churn and keep existing tests and call sites stable, Phase 1.X should:
- Keep `RLMConfig` as the public object returned by `load_rlm_config()`.
- Keep existing effective fields available for now.
- Add nested dataclass views (e.g., `config.budget`, `config.sandbox`, `config.llm`) used by constructors.

This still satisfies the roadmap requirement of nested config structures + nested TOML schema, while enabling a later "Phase 3" refactor to fully-nested internal storage if desired.

---

## Success Criteria

### Verification Commands
```bash
pytest tests/rlm/test_config.py -v
pytest tests/rlm -q
```

### Final Checklist
- [x] Nested `[rlm.*]` keys parse and override defaults.
- [x] Legacy flat keys still work and warn.
- [x] No env overrides added.
- [x] Pricing remains `[rlm.pricing]`.
- [x] Docs exist: `DOCS/reference/rlm-config.md`.
