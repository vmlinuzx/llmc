# Agent Prompt – Phase 4 Gateway / Gemini Config Integration

You are an implementation agent working on the LLMC repository.

Your goal in this phase is to wire gateway / Gemini behaviour in
`scripts/qwen_enrich_batch.py` to the enrichment configuration provided
by `tools.rag.config_enrichment.load_enrichment_config`.

## Objectives

1. For `selected_backend == "gateway"`, consult `enrichment_cfg.chain`
   to determine the desired gateway model for the current tier.
2. Set the `GEMINI_MODEL` environment variable for the duration of each
   gateway attempt, based on the matching `BackendConfig.model`.
3. Restore the environment afterwards so subsequent code is unaffected.
4. Preserve all existing router / retry / host rotation semantics.

## Files in this patch

- `scripts/qwen_enrich_batch.py`
  - Minor modifications only.
- `DOCS/RAG_ENRICHMENT/SDD_Enrichment_Gateway_Config_Phase4.md`
- `DOCS/RAG_ENRICHMENT/SDD_Enrichment_Gateway_Config_Phase4_Impl.md`

## Implementation Checklist

1. Locate the main enrichment loop in `scripts/qwen_enrich_batch.py`:
   - Specifically, the `while attempt_idx < max_attempts:` block where
     `call_qwen` is invoked.

2. Just before the existing `try: stdout, meta = call_qwen(...)`, add:
   - Local flags `gateway_model_env_changed` and `gateway_model_prev`.
   - A lookup on `enrichment_cfg.chain` using
     `_select_backend_config_for_tier`, first with `provider="gemini"`
     then `provider="gateway"`.
   - If a matching config is found and has a `model`, capture the
     previous `GEMINI_MODEL` value and set a new one.

3. Transform the simple `try/except RuntimeError` around `call_qwen`
   into a `try/except/finally` where:
   - The `except` block is unchanged (same runtime failure handling).
   - The `finally` block checks `gateway_model_env_changed` and restores
     the previous `GEMINI_MODEL` value (or deletes it).

4. Verify imports:
   - `os` is already imported at the top of the file; no changes needed.
   - `_select_backend_config_for_tier` is already defined above
     `health_check_ollama_hosts` (from Phase 3).

5. Run basic smoke tests:
   - `python3 scripts/qwen_enrich_batch.py --help`
   - `python3 scripts/qwen_enrich_batch.py --dry-run --backend gateway --router off`
   - With and without an `enrichment.chain` gateway entry in `llmc.toml`.

## Git / Review Guidance

- Create a branch such as `feature/enrich-config-phase4-gateway`.
- Commit the changes in a single logical diff:
  - `scripts/qwen_enrich_batch.py`
  - New docs under `DOCS/RAG_ENRICHMENT/`.
- Suggested commit message:

  > chore(enrich): drive gateway model from llmc.toml

- Request review from the RAG/enrichment maintainer.
