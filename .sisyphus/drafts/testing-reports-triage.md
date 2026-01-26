# Draft: Testing Reports Triage

## Original Request
- Look at the recent testing reports and build a plan to resolve.

## Requirements (unconfirmed)
- Identify the current failing tests (names, counts, error messages, flakes vs deterministic).
- Determine the test runner(s) and how tests are executed (local + CI / repo workflow).
- Propose a fix plan with ordering, risk, and verification steps.
- Clarify whether “resolve” includes static analysis (ruff/mypy) or is pytest-only.

## Requirements (confirmed)
- Target gate: make the **Ruthless Testing Workflow** green (per user choice).

## Technical Decisions
- None yet.

## Research Findings
- Test artifacts exist in-repo: `tests/REPORTS/current/` contains recent (2026-01-25) reports + logs.
- Test framework: pytest configured in `pyproject.toml` (`tool.pytest.ini_options`).
- Repo “CI” is agent/workflow driven (not GitHub Actions in this checkout): `.agent/workflows/ruthless-testing.md` defines the typical verification phases.
- `make test` runs: `ruff check .`, `mypy scripts/qwen_enrich_batch.py`, and `pytest` (see `Makefile`).

### Key Reports (most relevant)
- `tests/REPORTS/current/rem_testing_2026-01-25.md` (branch noted in report: `feat/rlm-config-nested-phase-1x`)
- `tests/REPORTS/current/feat_rlm_config_nested_phase_1x_test_report.md`
- `tests/REPORTS/current/full_run.log`
- `tests/REPORTS/current/pytest_rag_router.txt`
- `tests/REPORTS/current/rlm_config_test_run.log`

### Failures Observed (from reports)
- Security regression (CRITICAL): `tests/security/test_rlm_traversal_poc.py` and `tests/security/test_rlm_sandbox_escape_poc.py` are written as **POCs** that explicitly confirm the vuln via assertions/prints (i.e., they may “pass” while still indicating the system is insecure). Reports flag this as a security failure, not necessarily a pytest failure.
- MCP RLM config: `tests/mcp/test_rlm_config.py` fails 4/5 with `Failed: DID NOT RAISE pydantic_core.ValidationError` (tests expect Pydantic validation; implementation behaves like a dataclass without those errors).
- RAG router: report logs include a failing run (`pytest_rag_router.txt`), but later logs (`pytest_rag_router_fixed_2.txt`) show `55 passed` (may already be resolved on-branch; must verify current state first).
- Test collection error: `tests/agent/test_openai_compat_backend.py` fails to import `respx` (`ModuleNotFoundError: No module named 'respx'`).

### Code-Level Confirmation (read-only)
- `llmc/rlm/config.py` defaults `security_mode = "permissive"`.
- `llmc/rlm/session.py` reads any `Path` passed to `load_context` via `Path.read_text()` with no root/allowlist enforcement.
- `llmc_mcp/tools/rlm.py` performs path validation via `llmc_mcp.tools.fs.validate_path(...)`, but calls it with args (`allowed_roots`, `repo_root`, `operation`) that do not appear to match the current function signature (confirmed by `tests/REPRO_rlm_path_explosion.py`).
- `llmc_mcp/config.py` is dataclass-based with `.validate()` methods; current tests expect Pydantic-style `ValidationError` when wrong-typed dicts are passed directly to `McpConfig(**{...})`.

### Workflow/Test Policy Notes
- `DOCS/development/testing.md` says `tests/gap/` are expected to fail until features exist; treat separately from true regressions.
- `tests/_plugins/pytest_ruthless.py` exists; tests may require flags like `--allow-network` / markers.

## Scope Boundaries
- INCLUDE: triage + root-cause hypotheses + resolution plan for failures reflected in `tests/REPORTS/current/`.
- EXCLUDE (for now): implementing fixes; non-test-related refactors unless needed to fix failing suites.

## Open Questions
- Confirm baseline: should we treat `feat/rlm-config-nested-phase-1x` (named in reports) as the target branch, or plan for `main`/current HEAD?
- Priority: fastest green build vs security-first (recommended: security-first).
- Dependency policy: okay to add missing dev deps (e.g., `respx`) vs rewriting tests to avoid new deps.
