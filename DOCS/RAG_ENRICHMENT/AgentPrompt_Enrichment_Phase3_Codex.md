# Agent Prompt – Apply Phase 3 Enrichment Config Tier Overrides

You are an implementation agent working on the LLMC repository.

Your task is to apply the Phase 3 patch that tightens the integration
between `llmc.toml` enrichment config and the `scripts/qwen_enrich_batch.py`
runner.

## Objectives

1. Ensure that enrichment config (`load_enrichment_config`) can override
   default batch size, cooldown, and retries **when the user does not
   pass explicit CLI flags**.
2. Allow `[enrichment.chain]` entries with `provider="ollama"` to control
   the model/options/keep_alive/base URL used for the 7B/14B tiers.
3. Preserve all existing control flow, router behaviour, and host rotation
   semantics.

## Files in this patch

- `scripts/qwen_enrich_batch.py`
  - Adds `_select_backend_config_for_tier` helper.
  - Extends the enrichment config block near the top of `main()`.
  - Updates the backend selection block in the main enrichment loop to
    consult `enrichment_cfg.chain` for Ollama tiers.
- `DOCS/RAG_ENRICHMENT/SDD_Enrichment_Config_Tier_Overrides_Phase3.md`
- `DOCS/RAG_ENRICHMENT/SDD_Enrichment_Config_Tier_Overrides_Phase3_Impl.md`

## Implementation Checklist

1. Replace `scripts/qwen_enrich_batch.py` with the version from this
   patch.
   - Ensure imports still resolve:
     - `tools.rag.config_enrichment.load_enrichment_config` must be present.
   - Confirm `_select_backend_config_for_tier` is defined above
     `health_check_ollama_hosts`.
2. Verify the enrichment config block in `main()` matches the design:
   - It catches `ValueError` from `load_enrichment_config`.
   - It overrides `policy_default_tier` / `policy_fallback_tier` from
     config when present.
   - It only overrides `args.batch_size`, `args.cooldown`, and
     `args.retries` when they are still on their parser defaults.
3. Confirm the main loop’s backend selection:
   - For `tier_for_attempt` in `{ "7b", "14b" }` and `selected_backend == "ollama"`,
     check that `backend_cfg = _select_backend_config_for_tier(...)` is
     called.
   - Ensure `backend_cfg.options`, `.keep_alive`, `.model`, and `.url`
     are applied as described.
4. Run basic smoke tests:
   - `python3 scripts/qwen_enrich_batch.py --help` should work.
   - `python3 scripts/qwen_enrich_batch.py --dry-run --verbose` on a
     small repo with and without `llmc.toml`.

## Git / Review Guidance

- Create a feature branch, e.g. `feature/enrich-config-phase3`.
- Commit in a single logical change:
  - `scripts/qwen_enrich_batch.py`
  - New docs under `DOCS/RAG_ENRICHMENT/`.
- Use a descriptive commit message, e.g.:

  > chore(enrich): wire llmc.toml into qwen_enrich defaults & ollama tiers

- Open a PR and request review from the RAG / enrichment owner.
