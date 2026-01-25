# Draft: SDD Review - RLM Config Surface

Source SDD: `DOCS/planning/SDD_RLM_Config_Surface.md`

Goal of this draft: capture a critical review (corrections + improvements) so the SDD can be tightened before execution.

## High-Impact Corrections (must fix)

- **Non-portable file links**: The SDD uses absolute `file:///home/vmlinux/...` links (ex: `DOCS/planning/SDD_RLM_Config_Surface.md#L84`). These won\*t work on other machines or in GitHub. Use repo-relative paths like `llmc/rlm/config.py`.

- **CLI command in manual verification is incorrect**: The SDD says `llmc rlm "analyze this file" --file somefile.py`.
  - Actual CLI is a subcommand: `llmc rlm query "..." --file ...`.
  - Reference: `llmc/commands/rlm.py`.

- **BudgetConfig duplication/conflict**: The SDD proposes a new `BudgetConfig` in `llmc/rlm/config.py`, but `BudgetConfig` already exists.
  - Reference: `llmc/rlm/governance/budget.py`.
  - If duplicated, call sites become ambiguous and drift-prone.

- **TOML schema mismatch for pricing**:
  - Existing code loads pricing from `[rlm.pricing]`.
  - SDD proposes `[rlm.budget.pricing]`.
  - Reference: `llmc/rlm/governance/budget.py:load_pricing()`.

- **Nested dataclass redesign is likely breaking**:
  - Current `RLMConfig` is flat and is used directly by `RLMSession` and CLI code.
  - SDD proposes a fully nested structure (`RLMConfig.budget`, `RLMConfig.sandbox`, etc.).
  - Without an explicit compatibility layer, this will break internal consumers.
  - References: `llmc/rlm/config.py`, `llmc/rlm/session.py`, `llmc/commands/rlm.py`.

- **Missing factory wiring for sandbox config**:
  - SDD proposes passing `SandboxConfig` into `ProcessSandboxBackend.__init__`, but the sandbox factory currently passes primitives.
  - References: `llmc/rlm/sandbox/interface.py`, `llmc/rlm/sandbox/process_backend.py`.

- **Validation error type is undefined**: SDD references `ValidationError` but the codebase uses dataclasses + manual validation, typically raising `ValueError`.
  - Reference pattern: `llmc_mcp/config.py` (dataclasses + `.validate()` raising `ValueError`).

- **Test count and test list inconsistencies**:
  - SDD claims "Existing RLM tests still pass (17/17)"; current pytest suite has more than 17 tests.
  - SDD lists 4 tests in `test_config.py` but acceptance criteria demands >=8 tests.

- **Python 3.9+ compatibility must be explicit**:
  - Project requires `>=3.9` and depends on `tomli` for <3.11.
  - SDD sample code uses `tomllib` only.
  - Reference: `pyproject.toml` and the conditional import pattern in `llmc_agent/config.py`.

## Design Improvements (strongly recommended)

- **Adopt repo-standard config precedence**: explicitly define (and implement) precedence as:
  - defaults (dataclass fields)
  - `llmc.toml` `[rlm]` section
  - env overrides (`LLMC_RLM_*` suggested)
  - CLI flags (highest precedence)
  - Reference patterns: `llmc_mcp/config.py` and `llmc_agent/config.py`.

- **Centralize config path resolution**:
  - Current RLM code uses `Path("llmc.toml")` directly in places (ex: pricing load), which breaks when run outside repo root.
  - Prefer repo-root discovery via `llmc/core.py:find_repo_root()` and/or a consistent `LLMC_CONFIG` / `LLMC_ROOT` strategy.
  - References: `llmc/core.py`, `llmc_mcp/config.py`.

- **Key naming consistency**: reconcile these mismatches (either rename fields or document aliases):
  - `max_tokens_per_session` (current `RLMConfig`) vs `max_session_tokens` (SDD) vs `BudgetConfig.max_session_tokens`.
  - `max_print_chars` (current `RLMConfig`) vs `max_output_chars` (sandbox).

- **Explicit merge semantics**: define whether lists/sets replace vs merge.
  - `pricing`: likely merge into defaults.
  - `allowed_modules`/`blocked_builtins`: security-sensitive; decide whether config can only add items (safer) vs replace.

- **Security posture callout**:
  - Allowing arbitrary `allowed_modules` overrides can weaken the sandbox.
  - Recommend documenting guardrails (ex: default safe list, require explicit opt-in to expand beyond safe core).

## Test/Verification Improvements

- **Split tests by speed and secrets**:
  - Any test requiring `DEEPSEEK_API_KEY` should be clearly marked as integration/optional and skipped when unset.
  - Reference: pytest markers in `pyproject.toml`.

- **Config behavior tests to add (to reach >=8)**:
  - Missing file => defaults
  - Missing `[rlm]` section => defaults
  - Partial config => merges with defaults
  - Invalid types (string where int expected) => readable error
  - Negative budget => readable error
  - Unknown keys => either ignored-with-warning or hard error (must decide)
  - Precedence: TOML vs env vs CLI
  - Pricing override merges into defaults

## Concrete Edits to Apply to the SDD

- Replace absolute links with repo-relative paths.
- Fix manual verification command to `llmc rlm query ...`.
- Add a "Compatibility" section: clarify whether `RLMConfig` stays flat (recommended) or adds nesting with aliases.
- Align pricing schema with current implementation (`[rlm.pricing]`) or explicitly support both with migration note.
- Add explicit function signatures for parsing/validation (even if just pseudocode).
- Update acceptance criteria to be countable/testable (enumerate the exact hardcoded constants to move).

## Open Questions

- Should the work preserve the current *Python API surface* for `RLMConfig` (flat fields), or is a breaking change acceptable?
- Should pricing live under `[rlm.pricing]` (matches current code) or `[rlm.budget.pricing]` (more structured)?
- Should tracing default to enabled or disabled when running `llmc rlm query`?
