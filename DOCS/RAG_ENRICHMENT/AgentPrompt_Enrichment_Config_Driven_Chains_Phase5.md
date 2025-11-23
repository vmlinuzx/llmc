# Agent Prompt – Implement Config-Driven Enrichment Chains (Phase 5)

You are a senior implementation agent working on the LLMC repository.

Your task is to make enrichment backend/model selection driven by `llmc.toml`
and environment variables, using the provided patch files in this zip, and
following good Git/GitHub practices.

---

## Objectives

1. Add a dedicated enrichment configuration loader in `tools/rag/config_enrichment.py`.
2. Wire `scripts/qwen_enrich_batch.py` to use `EnrichmentConfig` + `BackendCascade`
   so that chains and tiers come from config instead of hard-coded presets.
3. Keep behaviour backwards compatible when no config is present.
4. Ensure tests pass and prepare the changes for a clean PR.

---

## Implementation Steps

1. **Create a working branch**

   Suggested branch name: `feature/enrichment-config-chains-phase5`

2. **Apply the patch contents**

   Extract this zip into the repo root, preserving paths:

   - `tools/rag/config_enrichment.py`
   - `scripts/qwen_enrich_batch.py`
   - `tests/test_enrichment_config.py`
   - `DOCS/RAG_ENRICHMENT/SDD_Enrichment_Config_Driven_Chains_Phase5.md`
   - `DOCS/RAG_ENRICHMENT/SDD_Enrichment_Config_Driven_Chains_Phase5_Impl.md`
   - `DOCS/RAG_ENRICHMENT/AgentPrompt_Enrichment_Config_Driven_Chains_Phase5.md`

   Ensure `tools/rag` is a package (it should already be).

3. **Review and adjust code as needed**

   - `tools/rag/config_enrichment.py`:
     - Implements `EnrichmentBackendSpec`, `EnrichmentConfig`, and
       `EnrichmentConfigError`.
     - Provides:
       - `load_enrichment_config(repo_root, toml_path=None, env=None)`
       - `select_chain(config, chain_name)`
       - `filter_chain_for_tier(chain, routing_tier)`
     - Handles:
       - `[enrichment]` and `[[enrichment.chain]]` in `llmc.toml`,
       - env overrides (`ENRICH_CHAIN_JSON`, `ENRICH_CONCURRENCY`,
         `ENRICH_COOLDOWN_SECONDS`),
       - default fallback when no TOML is present.

   - `scripts/qwen_enrich_batch.py`:
     - Imports the config helpers:
       - `EnrichmentConfig`, `EnrichmentBackendSpec`, `EnrichmentConfigError`,
         `load_enrichment_config`, `select_chain`, `filter_chain_for_tier`.
     - Extends `parse_args()` with:
       - `--chain-name`
       - `--chain-config` (hook `--chain-config` into `load_enrichment_config`
         later if desired; for now it is a placeholder flag for future wiring).
     - In `main()`:
       - Loads `enrichment_config` with `load_enrichment_config(repo_root=repo_root)`.
       - Uses `select_chain(enrichment_config, args.chain_name)` to get
         `selected_chain`.
       - Falls back cleanly to legacy behaviour on `EnrichmentConfigError`.
     - `_build_cascade_for_attempt(...)` now accepts:
       - `enrichment_config` and `selected_chain`.
       - When config is available, it uses `filter_chain_for_tier` to select
         a tier-specific subset and builds adapters from `EnrichmentBackendSpec`.
       - When config is missing or yields no tier entries, it falls back to the
         previous Phase 4 behaviour (preset + host chain).
     - The main attempt loop passes `enrichment_config` and `selected_chain`
       into `_build_cascade_for_attempt` and records `chain_name` metadata in
       attempt records where available.

4. **Run tests**

   From the repo root, run at minimum:

   ```bash
   python -m pytest tests/test_enrichment_config.py
   ```

   Then run your existing enrichment / RAG tests to ensure there are no
   regressions in behaviour.

5. **Smoke test enrichment with a sample config**

   Example `llmc.toml` snippet:

   ```toml
   [enrichment]
   default_chain = "default"

   [[enrichment.chain]]
   chain = "default"
   name = "athena-7b"
   provider = "ollama"
   model = "qwen2.5:7b-instruct-q4_K_M"
   url = "http://athena:11434"
   routing_tier = "7b"

   [[enrichment.chain]]
   chain = "default"
   name = "gemini-fast"
   provider = "gateway"
   model = "gemini-2.5-flash"
   routing_tier = "14b"
   ```

   Then run:

   ```bash
   python scripts/qwen_enrich_batch.py        --repo /path/to/repo        --chain-name default        --batch-size 3        --verbose
   ```

   Confirm that:

   - Small spans use the 7B Ollama backend.
   - Router promotion uses the 14B / gateway backend when appropriate.

6. **Git / GitHub hygiene**

   - Stage only intended files.
   - Use a descriptive commit message, e.g.:
     - `feat(rag): add config-driven enrichment chains (phase 5)`
   - Open a PR with:
     - Summary of config-driven chains.
     - Links to the SDD and Implementation SDD.
     - Tests executed and their results.

---

## Acceptance Criteria

- `qwen_enrich_batch` uses config-driven chains when `[enrichment]` is defined,
  and falls back to legacy behaviour when it is not.
- `tools.rag.config_enrichment` is the single source of truth for enrichment
  configuration.
- Unit tests for `config_enrichment` pass, and existing enrichment tests are
  green or adjusted with clear rationale.
