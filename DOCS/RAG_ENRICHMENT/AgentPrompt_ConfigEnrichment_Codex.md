# Agent Prompt – Apply Config Enrichment Patch

You are a coding agent working on the LLMC repository.

Your task in this session is to **add the enrichment configuration loader** and its tests, following best GitHub and Python practices.

## Context

- Repo root contains:
  - `tools/rag/config.py`
  - `tools/rag/enrichment.py`
  - `scripts/qwen_enrich_batch.py`
  - `tests/` with existing enrichment tests
- We want to introduce a new, focused module that owns enrichment config parsing, without changing existing behaviour yet.

## Goals

1. Add `tools/rag/config_enrichment.py` implementing:
   - `BackendConfig`
   - `EnrichmentConfig`
   - `load_enrichment_config(repo_root: Optional[Path] = None, env: Mapping[str, str] | None = None)`
   - Defaults and validation exactly as described in the SDDs.
2. Add `tests/test_enrichment_config.py` with pytest tests for:
   - default behaviour when `llmc.toml` is missing,
   - parsing values from TOML,
   - env overrides for scalars,
   - `ENRICH_CHAIN_JSON` override,
   - invalid provider handling.

## Implementation Steps

1. **Create a feature branch**
   - Branch name suggestion: `feature/enrichment-config-loader`.
   - Example:
     - `git checkout -b feature/enrichment-config-loader`

2. **Add the new module**
   - Create `tools/rag/config_enrichment.py`.
   - Copy the implementation from the provided patch (do not hand-edit unless necessary).
   - Ensure imports are relative (`from .config import load_config, get_est_tokens_per_span`).

3. **Add tests**
   - Create `tests/test_enrichment_config.py`.
   - Use `tmp_path` fixtures to create temporary repos with custom `llmc.toml` files.
   - Do not depend on any existing on-disk state or network calls.

4. **Run tests locally**
   - At minimum:
     - `python -m pytest tests/test_enrichment_config.py`
   - If feasible, run the broader enrichment suite:
     - `python -m pytest tests/test_enrichment_*.py tools/rag/tests/test_enrichment_db_helpers.py`

5. **Code quality**
   - Follow existing formatting (PEP8 / black style).
   - Keep functions small and focused (one responsibility per helper).
   - Use clear, actionable error messages for `ValueError` cases.

6. **GitHub best practices**
   - Keep commits small and coherent (e.g., one commit for new module, one for tests).
   - Write descriptive commit messages, e.g.:
     - `feat: add enrichment config loader`
     - `test: add unit tests for enrichment config loader`
   - Push the branch and open a pull request with:
     - Summary of changes
     - Notes on testing (`pytest` commands run and results)
     - Any follow-up work (e.g., wiring `load_enrichment_config` into `qwen_enrich_batch.py`).

## Acceptance Criteria

- `tools/rag/config_enrichment.py` exists and can be imported.
- `load_enrichment_config` returns an `EnrichmentConfig` with sensible defaults when no config is present.
- TOML and env overrides behave as described in the SDD.
- `pytest tests/test_enrichment_config.py` passes.
- No existing tests are broken.
