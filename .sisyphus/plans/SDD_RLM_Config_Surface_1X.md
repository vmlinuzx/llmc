# SDD: RLM Configuration Surface Implementation (1.X)

Status: PLANNED
Priority: P0 (Critical)
Effort: 1-2 days
Difficulty: Medium

## 0. Context

RLM currently has many hardcoded values spread across multiple modules. This blocks real-world deployments (including hospital environments) because cost limits, timeouts, model selection, and sandbox policy cannot be controlled via configuration.

Existing reference roadmap item: `DOCS/ROADMAP.md:701`
Existing earlier SDD (superseded by this one): `DOCS/planning/SDD_RLM_Config_Surface.md`

This SDD captures the updated requirements from this planning session:
- Nested config structures (not purely flat)
- Hybrid validation (hard-fail critical; warn+default non-critical)
- Security policy MUST be configurable (default permissive for local dev; restrictive for hospital deployments)
- No environment variable overrides (config-file-only)
- TDD required

## 1. Goals

- Implement a robust `load_rlm_config()` that loads `llmc.toml` `[rlm]` settings using LLMC's standard config discovery.
- Externalize all RLM hardcoded values (audit found 92) into `llmc.toml` and/or config defaults.
- Provide a hospital-grade validation story:
  - Critical misconfiguration fails fast with clear errors
  - Non-critical misconfiguration warns and falls back to safe defaults
- Make sandbox policy configurable:
  - Developer-friendly permissive defaults for local use
  - Strict, allowlist-based policy for hospital environments
- Thread config through all RLM components (including `TreeSitterNav`, currently missing).
- Document the full schema and provide example configs.

## 2. Non-Goals

- Runtime hot-reload of configuration
- Config file watching / auto-reload on change
- GUI/TUI config editor
- Environment-variable overrides (`LLMC_RLM_*`)
- Automatic migration / rewriting of existing `llmc.toml` files
- Adding a dedicated "validate config" CLI command (nice-to-have later)
- Changing the overall RLM session loop behavior beyond replacing constants with config

## 3. Current State (Code References)

Key files and the relevant issues:

- `llmc/core.py`
  - Contains LLMC standard config discovery and TOML loading utilities; RLM config loading should reuse these (avoid inventing a new discovery mechanism).

- `DOCS/user-guide/configuration.md`
  - Documents repo-wide configuration conventions (TOML, sections, examples).

- `llmc/rlm/config.py`
  - Has `RLMConfig` dataclass and `load_rlm_config()`, but parsing/validation behavior is incomplete and contains TODO-ish logic.
  - Uses `data.pop("sandbox", {})` which mutates the dict.

- `llmc/rlm/session.py`
  - Threads config into budget + sandbox, but not navigation.
  - Has multiple hardcoded limits in tool helpers (context_search truncation, preview sizes, etc.).

- `llmc/rlm/nav/treesitter_nav.py`
  - Constructor does not accept config.
  - Hardcoded defaults: language="python", read/search limits, preview truncation, token estimation (`// 4`).

- `llmc/rlm/sandbox/process_backend.py`
  - Implements controlled import via allowlist (`ALLOWED_MODULES`).
  - Needs a "permissive" mode (e.g., allow all imports) without weakening hospital deployments.

- `llmc/rlm/governance/budget.py`
  - Has DEFAULT_PRICING and some repeated defaults.
  - Pricing is already partially configurable via `[rlm.pricing]`.

Existing tests:
- `tests/rlm/test_config.py` (currently expects ValueError for negative budget)
- `tests/rlm/test_nav.py`
- `tests/rlm/test_sandbox.py`
- `tests/rlm/test_budget.py`

## 4. Proposed Design

### 4.1 Config Model (Python)

Introduce nested dataclass structures while keeping backwards-compatible access for internal consumers.

Design principle: minimize blast radius.

- Keep `RLMConfig` as the single object passed around (e.g., `RLMSession(config)` already exists).
- Add nested sections as fields on `RLMConfig` (budget/sandbox/llm/nav/session/token_estimate/trace/limits).
- Provide thin compatibility properties (only if needed) to avoid touching too many callsites at once.

Minimum section set:

1) Budget
- Max USD
- Max tokens
- Soft limit percentage
- Max subcall depth
- Pricing table

2) Sandbox
- Backend
- Code timeout
- Max output chars
- Security policy mode: permissive|restrictive
- blocked_builtins
- allowed_modules (used in restrictive mode)
- terminate grace seconds (join timeout)

3) LLM call params
- root/sub model names
- root/sub temperature
- root/sub max_tokens

4) Nav
- default_language
- outline_max_depth
- read_max_chars
- search_max_results
- signature_preview_chars
- match_preview_chars
- symbol_list_limit
- token_estimate_chars_per_token (re-use token_estimate)

5) Session + tool UX limits
- session_timeout_seconds
- max_turns
- context_search_default_max_results
- context_search_match_preview_chars

6) Token estimation
- chars_per_token
- token_safety_multiplier

7) Trace
- trace_enabled
- preview limits (stdout/stderr/prompt/response) currently hardcoded in `llmc/rlm/session.py`

### 4.2 TOML Schema

Use nested TOML for readability. Example:

```toml
[rlm]

[rlm.llm]
root_model = "ollama_chat/qwen3-next-80b"
sub_model  = "ollama_chat/qwen3-next-80b"

[rlm.llm.root]
temperature = 0.1
max_tokens  = 4096

[rlm.llm.sub]
temperature = 0.1
max_tokens  = 1024

[rlm.budget]
max_session_budget_usd = 1.00
max_session_tokens     = 500000
soft_limit_percentage  = 0.80
max_subcall_depth      = 5

[rlm.pricing]
default = { input = 0.01, output = 0.03 }
"ollama_chat/qwen3-next-80b" = { input = 0.0, output = 0.0 }

[rlm.sandbox]
backend            = "process"
code_timeout_seconds = 30
max_output_chars     = 10000
security_mode        = "permissive"  # dev default; hospital uses "restrictive"
terminate_grace_seconds = 1

[rlm.sandbox.policy]
blocked_builtins = ["open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "exit", "quit"]
allowed_modules  = ["json", "re", "math", "collections", "itertools", "functools", "operator", "string", "textwrap", "datetime", "copy", "typing", "dataclasses"]

[rlm.nav]
default_language = "python"
outline_max_depth = 3
read_max_chars = 8000
search_max_results = 20
signature_preview_chars = 200
match_preview_chars = 200
symbol_list_limit = 20

[rlm.session]
session_timeout_seconds = 300
max_turns = 20

[rlm.tools.context_search]
default_max_results = 20
match_preview_chars = 200

[rlm.token_estimate]
chars_per_token = 4
token_safety_multiplier = 1.2

[rlm.trace]
enabled = true
prompt_preview_chars = 200
response_preview_chars = 200
assistant_preview_chars = 500
stdout_preview_chars = 2000
stderr_preview_chars = 500
```

Note: We keep `[rlm.pricing]` where it already exists today (`llmc/rlm/governance/budget.py:36-53`).

### 4.3 Security Policy Semantics

We need permissive local use without preventing hospital-hardening.

Define `rlm.sandbox.security_mode`:

- restrictive:
  - Enforce allowlist imports via `allowed_modules` (current behavior in `ProcessSandboxBackend._make_controlled_import()`)
  - Enforce blocked builtins (denylist)

- permissive:
  - Still enforce blocked builtins (denylist), but allow imports broadly
  - Implementation detail: treat `allowed_modules = None` as "allow all imports" in `ProcessSandboxBackend._make_controlled_import()`.

This keeps the safety story reasonable while enabling local experimentation.

### 4.4 Validation Strategy (Hybrid)

Validation tiers:

Hard-fail (raise ValueError with actionable message):
- Budget: negative USD, negative tokens, soft_limit not in (0,1], max_subcall_depth < 0
- Pricing: missing required keys, negative prices, non-numeric prices
- LLM: missing/empty root_model or sub_model
- Sandbox: unknown backend, unknown security_mode, blocked_builtins not a list of strings
- Token estimation: chars_per_token < 1, safety_multiplier <= 0

Warn+default (log warning, use default):
- Timeouts: session/code timeout out of range
- UX limits: preview truncation sizes, read/search limits
- Language defaults

Implementation requirement:
- `load_rlm_config()` returns a config that is always safe to use.

Warning handling decision (default):
- Warn+default uses the logger (recommended for simplicity).
- Tests must assert warnings via `caplog` when invalid-but-noncritical values are provided.

### 4.5 Inventory of "Hardcoded Values" (92)

The executor must ensure each hardcoded value is either:
- moved into config structure (TOML + defaults), or
- explicitly justified as non-configurable (rare; must be documented).

Important: the "92" count must be made verifiable.

If a standalone audit list does not already exist, the executor MUST generate a baseline inventory first (and keep it up to date during the work):
- Use `rg`/AST search to enumerate numeric/string literals in `llmc/rlm/` excluding tests.
- Manually triage which literals are true config knobs vs legitimate constants.
- Record justified exceptions (e.g., prompt text, algorithm constants) in a short appendix section in this SDD or a dedicated audit doc.

Audit sources:
- `llmc/rlm/config.py`
- `llmc/rlm/governance/budget.py`
- `llmc/rlm/sandbox/process_backend.py`
- `llmc/rlm/session.py`
- `llmc/rlm/nav/treesitter_nav.py`
- `llmc/rlm/sandbox/interface.py`
- `llmc/rlm/prompts.py` (prompt text is mostly fine to remain hardcoded; prompt formatting knobs can be optional)

## 5. Implementation Plan (TDD)

### 5.0 Baseline Verification

Before changes:
- Run `pytest tests/rlm/test_config.py -v`
- Run `pytest tests/rlm/test_nav.py -v`

Also recommended (baseline safety net):
- Run `pytest tests/rlm/ -v`

Hardcoded-inventory baseline (to make the "92" target verifiable):
- Capture a baseline list of candidate literals in `llmc/rlm/` (excluding tests) and store it in a scratch artifact for comparison during the work.
- Minimum command set (executor can refine):
  - `rg -t py '=[^\n]*\b\d+\b' llmc/rlm/ | rg -v '/test_'`
  - `rg -t py '=[^\n]*"[^"]+"' llmc/rlm/ | rg -v '/test_'`

### 5.1 Config Model + Parsing

Modify `llmc/rlm/config.py`:
- Add nested dataclasses
- Implement parsing from dict (do not mutate input dict; avoid `pop()` side effects)
- Implement hybrid validation (critical errors raise; non-critical warn+default)
- Preserve existing behavior for these tests:
  - `tests/rlm/test_config.py::test_negative_budget_raises_valueerror` remains a hard-fail

Acceptance (unit):
- New tests prove nested TOML parsing works for each section.
- Unknown keys remain ignored.
- Add a regression test proving parsing does not mutate the caller-provided dict.
- Add a regression test proving warn+default paths emit a warning (assert via `caplog`).

### 5.2 Thread Config Through RLMSession

Modify `llmc/rlm/session.py`:
- Replace hardcoded tool limits in `_make_context_search()` with config values
- Replace any remaining magic numbers for token estimation with config
- Ensure config-based session timeout uses config (already does)

Acceptance (unit):
- Existing tests still pass

### 5.3 Thread Config Through TreeSitterNav

Modify `llmc/rlm/nav/treesitter_nav.py`:
- Add optional config argument (internal callsites only):
  - Before modifying signature, verify callsites via `rg "TreeSitterNav\(" --type py`.
  - Current expected callsites are: `llmc/rlm/session.py` and `tests/rlm/test_nav.py`.
- Use config.nav values for:
  - default language
  - outline depth
  - read max chars
  - search max results
  - signature/match preview truncation
  - symbol list limit
  - token estimation (replace `// 4`)

Update `llmc/rlm/session.py` to pass config
Update `tests/rlm/test_nav.py` to pass config or rely on defaults.

Acceptance (unit):
- `pytest tests/rlm/test_nav.py -v` passes
- `rg "TreeSitterNav\(" --type py` shows no broken callsites after the signature change

### 5.4 Sandbox Permissive/Restrictive Policy

Modify `llmc/rlm/sandbox/process_backend.py`:
- Support permissive mode by allowing `allowed_modules = None`:
  - In restrictive mode: keep current allowlist behavior
  - In permissive mode: allow import of any module name (still keep blocked builtins)

Acceptance (unit):
- Add tests validating restrictive blocks imports and permissive allows a representative safe import.
- Add tests validating blocked builtins are enforced in BOTH modes.

Suggested concrete test semantics (avoid relying on external network):
- Restrictive:
  - `allowed_modules = ["json"]` allows `import json`
  - `import os` fails
- Permissive:
  - `import os` succeeds
  - `open("/etc/passwd")` (or any `open(...)`) still fails

### 5.5 Budget Pricing Consolidation

Modify `llmc/rlm/governance/budget.py`:
- Ensure pricing source of truth is `[rlm.pricing]` with defaults.
- Ensure invalid pricing is a hard-fail (critical).

Acceptance (unit):
- Tests for pricing parsing and validation

### 5.6 Documentation

Create/Update:
- `DOCS/reference/config/rlm.md` (new) with full schema + examples
- `DOCS/reference/config/index.md` to link `rlm.md`
- `docker/deploy/mcp/llmc.toml.example` add a complete `[rlm]` example

Acceptance:
- Docs show:
  - minimal config
  - permissive local config
  - restrictive hospital config

Additional requirement:
- Example configs should be runnable/testable (prefer fixtures under `tests/fixtures/` and tests that load them).

Suggested fixture set (names are flexible; keep them stable once introduced):
- `tests/fixtures/rlm_config_minimal.toml`
- `tests/fixtures/rlm_config_local_permissive.toml`
- `tests/fixtures/rlm_config_hospital_restrictive.toml`

Suggested tests:
- In `tests/rlm/test_config.py`, add a parametrized test that loads each fixture and asserts:
  - load succeeds
  - critical values are applied
  - permissive/restrictive semantics are reflected in config fields

## 6. Test Plan

Framework: pytest (existing)

New/updated tests:
- `tests/rlm/test_config.py`
  - nested TOML parsing
  - hybrid validation: critical fail vs warn+default
  - permissive vs restrictive config loads

- `tests/rlm/test_nav.py`
  - still passes after TreeSitterNav signature change
  - add a test verifying config-driven limits (e.g., read_max_chars)

- (If exists/appropriate) new tests for sandbox import policy:
  - restrictive blocks import
  - permissive allows import

- `tests/rlm/test_sandbox.py`
  - extend to cover permissive vs restrictive semantics explicitly
  - assert blocked builtins still fail (e.g., `open()`)

Verification commands (minimum):
- `pytest tests/rlm/test_config.py -v`
- `pytest tests/rlm/test_nav.py -v`
- `pytest tests/rlm/test_sandbox.py -v`
- `pytest tests/rlm/test_budget.py -v`

## 7. Rollout / Backward Compatibility

- Config-file-only: no env overrides.
- Missing `[rlm]` section must preserve current defaults.
- TreeSitterNav signature change is internal only; keep new param optional.

## 8. Acceptance Criteria

- `load_rlm_config()` loads `[rlm]` from llmc.toml using LLMC standard discovery (`llmc.core.find_repo_root`, `llmc.core.load_config`).
- All hardcoded values (audit target: 92) are configurable via `llmc.toml` or well-justified exceptions.
- Hybrid validation implemented:
  - Critical misconfig -> ValueError with actionable message
  - Non-critical misconfig -> warning + safe default
- Security policy configurable:
  - default permissive usable locally
  - restrictive mode enforceable for hospital deployments
- TreeSitterNav configurable limits (no remaining `// 4`, `[:200]`, `max_results=20` hardcodes for behavior).
- Tests:
  - `pytest tests/rlm/test_config.py -v` passes
  - `pytest tests/rlm/test_nav.py -v` passes

Additional final verification:
- `pytest tests/rlm/ -v` passes
- No remaining hardcoded behavior-limit literals in `llmc/rlm/` for the knobs we explicitly made configurable (executor should verify with targeted `rg` searches for known magic patterns like `// 4`, `max_results=20`, `[:200]`).
