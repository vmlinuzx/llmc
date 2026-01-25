# Draft: RLM Nested Config Refactor

## Requirements (confirmed)
- Refactor `llmc/rlm/config.py` from a flat `RLMConfig` mapping into a deeply nested configuration system.
- Phase 1.X (P0) explicitly requires nested sections such as `[rlm.budget]`, `[rlm.llm]`, `[rlm.nav]`.
- Goal is to expose 80+ currently hardcoded values (examples: pricing tables, per-model params, token estimation rules) via config with granular overrides.

## Requirements (in discussion)
- Consider a migration path that may involve a separate config file for RLM (so we can improve config tooling later without blocking Phase 1.X).
- Consider whether JSON would be a better config format long-term.

## Requirements (confirmed)
- `llmc.toml` is canonical; RLM config will live under nested `[rlm.*]` sections.
- Migration approach: user will gradually move other configs/values into `[rlm.*]` over time.

## Technical Decisions
- Planning depth: Single execution plan with SDD appendix.
- Config file strategy: `llmc.toml` remains canonical/default; implement nested `[rlm.*]` sections per roadmap.
- Precedence for legacy vs nested: nested wins; emit deprecation warning when legacy flat keys are used or conflict.
- Env overrides: NO (Phase 1.X is TOML-only).
- Test strategy: YES, TDD (pytest).
- Pricing config location (Phase 1.X): keep canonical as `llmc.toml [rlm.pricing]` (current behavior). Defer `[rlm.budget.pricing]` migration to a later phase.
- `load_rlm_config()` return type: keep returning `RLMConfig` (public API stable). Implementation approach (Phase 1.X): keep existing flat fields as the canonical "effective" values, and add nested dataclass *views* (e.g., `config.budget`, `config.sandbox`, `config.llm`, `config.trace`) so we get nested structure without breaking existing call sites/tests. (A later phase can fully nest internal storage if desired.)
- Budget config type: reuse existing `llmc/rlm/governance/budget.py:BudgetConfig` as `RLMConfig.budget` (avoid duplicate classes / import cycles).
- Deprecation warnings: use Python `warnings.warn(..., DeprecationWarning, stacklevel=2)`; warn on legacy key usage and on legacy-vs-nested conflicts; prefer de-duping warnings per key per load.
- Overrides: TOML-only for Phase 1.X (no env overrides). Support `load_rlm_config(config_path=...)` for explicit file/directory selection.

## Research Findings
- Roadmap requirement is explicit: `DOCS/ROADMAP.md` includes Phase `1.X RLM Configuration Surface Implementation (P0)` and provides target nested dataclass shapes + TOML layout (including `[rlm.budget]`, `[rlm.nav]`, etc.).
- Current implementation is not a pure stub anymore, but it is still *flat*:
  - `llmc/rlm/config.py` defines a flat `RLMConfig` dataclass with many defaults (budget, timeouts, token estimation, sandbox policy, trace preview limits).
  - `load_rlm_config()` loads TOML, reads `[rlm]` and `[rlm.sandbox]`, and maps keys by matching dataclass field names.
  - Validation is minimal (range checks only); type mismatches fail indirectly (e.g. string compared to int).
- Pricing config is currently separate from `RLMConfig`:
  - `llmc/rlm/governance/budget.py:load_pricing()` reads `llmc.toml [rlm.pricing]` and merges into `DEFAULT_PRICING`.
  - Roadmap example TOML shows pricing under `[rlm.budget.pricing]`, so we likely need a compatibility/migration decision.
- Wiring today is partially config-driven but still flat:
  - `llmc/rlm/session.py` constructs `BudgetConfig` from `RLMConfig` flat fields and loads pricing separately; sandbox is created from flat fields; nav uses the same `RLMConfig` object.
- Test infrastructure exists and covers current behavior:
  - `pyproject.toml` declares `pytest` in `[project.optional-dependencies].dev` and pytest settings in `[tool.pytest.ini_options]`.
  - `tests/rlm/test_config.py` asserts defaults, partial merges, sandbox overrides, unknown keys ignored, and invalid type handling.
  - Additional RLM tests exist (`tests/rlm/test_budget.py`, etc.) that should guide refactor safety.
- Existing nested-config pattern elsewhere in repo:
  - `llmc/te/config.py` reads nested sections like `[tool_envelope.workspace]`, `[tool_envelope.telemetry]`, etc. (good precedent for nested TOML parsing + defaults).

## Open Questions
- What is the authoritative list of “80+ hardcoded values” for Phase 1.X, and where do they live today? (Expected to be resolved by inventory tasks during execution.)

## Scope Boundaries
- INCLUDE: Nested config structure definition, migration from current flat mapping, wiring config to replace hardcoded values.
- EXCLUDE (for now): Any behavioral changes unrelated to config plumbing (unless required to expose values).

## Plan Output
- Plan generated: `.sisyphus/plans/rlm-config-surface-phase-1x.md`
