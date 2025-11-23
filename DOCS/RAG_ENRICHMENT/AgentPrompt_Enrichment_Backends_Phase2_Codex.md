# Agent Prompt – Implement Enrichment Backends & qwen_enrich Wiring (Phase 2)

You are a coding agent working on the LLMC repository.

Your task is to **add the enrichment backend cascade module** and perform a **minimal, safe refactor** of `scripts/qwen_enrich_batch.py` to consume the new enrichment config loader for router tiers and model defaults.

## Inputs

You are provided with a patch zip that contains:

- `tools/rag/enrichment_backends.py`
- `tests/test_enrichment_cascade.py`
- Updated `scripts/qwen_enrich_batch.py`
- SDDs in `DOCS/RAG_ENRICHMENT/`

Treat the code in the patch as the source of truth for this change.

## Goals

1. Add `tools/rag/enrichment_backends.py` implementing:
   - `BackendError`
   - `BackendAdapter` protocol
   - `AttemptRecord`
   - `BackendCascade`
2. Add `tests/test_enrichment_cascade.py` with unit tests for the cascade.
3. Update `scripts/qwen_enrich_batch.py` to:
   - Import `DEFAULT_7B_MODEL`, `DEFAULT_14B_MODEL`, and `load_enrichment_config` from `tools.rag.config_enrichment`.
   - Remove local definitions of `DEFAULT_7B_MODEL` / `DEFAULT_14B_MODEL`.
   - Call `load_enrichment_config(repo_root)` in `main()` and allow it to override router `default_tier` / `fallback_tier`, logging the configured chain when `--verbose` is set.

## Implementation Checklist

1. **Branching**
   - Create a feature branch, e.g.:
     - `git checkout -b feature/enrichment-backends-phase2`

2. **Apply the patch**
   - Add the new files into the repo at the paths indicated.
   - Replace `scripts/qwen_enrich_batch.py` with the patched version from the zip (or apply the diff carefully).

3. **Run tests**
   - At minimum:
     - `python -m pytest tests/test_enrichment_cascade.py`
   - Recommended:
     - `python -m pytest tests/test_enrichment_config.py`
     - `python -m pytest tests/test_enrichment_*.py`

4. **Code quality**
   - Ensure imports are correct and there are no obvious style violations.
   - Keep the cascade module backend-agnostic (no direct imports from `scripts/`).

5. **GitHub best practices**
   - Commit in logical chunks:
     - `feat: add enrichment backend cascade module`
     - `feat: wire enrichment config into qwen_enrich router tiers`
     - `test: add unit tests for enrichment backend cascade`
   - Open a PR describing:
     - What changed (new module, router tier overrides, moved default model constants)
     - How it was tested (pytest commands)
     - Follow-up work (Phase 3: using BackendCascade in the main enrichment loop).

## Acceptance Criteria

- `tools/rag/enrichment_backends.py` is present and importable.
- `tests/test_enrichment_cascade.py` passes.
- `scripts/qwen_enrich_batch.py` compiles and continues to behave as before, except:
  - default/fallback tiers can now be overridden via `[enrichment]` in `llmc.toml`.
  - default model constants now live in `tools.rag.config_enrichment`.
- No existing tests are broken.
