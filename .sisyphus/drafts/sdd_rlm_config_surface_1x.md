# Draft: SDD RLM Config Surface 1X

## Requirements (confirmed)
- User requested: create/ensure a work plan at `.sisyphus/plans/SDD_RLM_Config_Surface_1X.md`.
- Config surface is TOML-based via `llmc.toml` under `[rlm]` and nested subsections.
- Nested config structures required (not purely flat).
- Hybrid validation required: hard-fail critical misconfig; warn+default for non-critical.
- Sandbox security policy must be configurable (permissive local dev default; restrictive hospital mode).
- No environment variable overrides for RLM config (config-file-only).
- TDD required (pytest).

## Technical Decisions
- Config format: TOML, discovered/loaded via LLMC standard config discovery.
- Config model: Python dataclasses (existing repo pattern).
- Validation: two-tier (raise on critical; warn+default on non-critical); warnings should be observable (logger or attached list).
- Testing: pytest; keep existing tests passing and add coverage for new sections.

## Research Findings
- RLM in this repo = "Recursive Language Model" subsystem (see `llmc/rlm/session.py`, `llmc/commands/rlm.py`).
- RLM config entrypoint and dataclass already exist (needs completion): `llmc/rlm/config.py`.
- Config conventions repo-wide: TOML + dataclasses; docs live in `DOCS/user-guide/configuration.md`.
- Test infrastructure exists: pytest with strict hermetic defaults; see `pyproject.toml`, `tests/conftest.py`, `DOCS/development/testing.md`.
- Existing plan at target path already contains detailed SDD-level tasks and acceptance criteria: `.sisyphus/plans/SDD_RLM_Config_Surface_1X.md`.
- Metis review identified critical gaps (audit verifiability, warning handling, callsite verification, sandbox acceptance tests); plan updated to address these.

## Open Questions
- None blocking. (Open question only if user wants env overrides or different config format.)

## Scope Boundaries
- INCLUDE: RLM config parsing/loading; threading config through session/nav/sandbox/budget; docs + examples; pytest coverage.
- EXCLUDE: hot reload; GUI/TUI editor; env-var overrides; behavior changes beyond replacing hardcoded constants.
