# Implementation SDD – Enrichment Config Loader

## 1. Files Touched

- **New**
  - `tools/rag/config_enrichment.py`
  - `tests/test_enrichment_config.py`

No existing files are modified in this patch.

## 2. Implementation Plan

### 2.1 `tools/rag/config_enrichment.py`

1. **Imports and defaults**
   - Import `dataclasses`, `json`, `os`, `Path`, typing helpers.
   - Import `load_config` and `get_est_tokens_per_span` from `tools.rag.config`.
   - Define scalar defaults:
     - `DEFAULT_CONCURRENCY = 1`
     - `DEFAULT_COOLDOWN_SECONDS = 0`
     - `DEFAULT_BATCH_SIZE = 50`
     - `DEFAULT_MAX_RETRIES_PER_SPAN = 3`
     - `DEFAULT_TIER = "7b"`
     - `DEFAULT_FALLBACK_TIER = "14b"`
   - Define model defaults:
     - `DEFAULT_7B_MODEL = "qwen2.5:7b-instruct-q4_K_M"`
     - `DEFAULT_14B_MODEL = "qwen2.5:14b-instruct-q4_K_M"`
   - Allowed providers: `_ALLOWED_PROVIDERS = {"ollama", "gateway"}`.

2. **Dataclasses**
   - Implement `BackendConfig` with fields and docstring as described in the main SDD.
   - Implement `EnrichmentConfig` with fields and docstring.
   - Export via `__all__` together with `load_enrichment_config`, `DEFAULT_7B_MODEL`, `DEFAULT_14B_MODEL`.

3. **Helpers**
   - `_env_int(env, name, default)`: safe int parsing from a mapping; returns `default` on missing/invalid values.
   - `_ensure_list(value, source)`: validate that `value` is a non-empty list of dicts; raise `ValueError` with context otherwise.
   - `_parse_chain(raw_chain)`: convert list of dicts into `BackendConfig` instances with validation:
     - enforce `name` and `provider`
     - provider membership in `_ALLOWED_PROVIDERS`
     - coercion for `timeout_seconds` and `max_retries`
     - `options` must be dict if present; else default `{}`
   - `_build_default_chain()`: returns 2 `BackendConfig` entries for 7B and 14B as per defaults.

4. **`load_enrichment_config` main function**
   - Accept `repo_root: Optional[Path]` and `env: Mapping[str, str] | None`.
   - Determine `env_map = env or os.environ`.
   - Load `cfg = load_config(repo_root)`.
   - Extract `enrichment_cfg = cfg.get("enrichment") or {}` when `cfg` is a dict; otherwise `{}`.
   - Compute scalar fields with env overrides:
     - `concurrency`, `cooldown_seconds`, `batch_size`, `max_retries_per_span` via `_env_int`.
   - Compute `est_tokens_per_span` using `get_est_tokens_per_span(repo_root)`.
   - Compute `default_tier` / `fallback_tier` from `enrichment_cfg` with string defaults.
   - Determine raw chain source:
     - If `ENRICH_CHAIN_JSON` is set in `env_map`, `json.loads` it and pass to `_ensure_list` with source `"ENRICH_CHAIN_JSON"`.
     - Else, inspect `enrichment_cfg.get("chain")` and either:
       - pass to `_ensure_list` with source `"enrichment.chain"`, or
       - treat as `None` if absent.
   - If `raw_chain is None`: construct chain via `_build_default_chain()`.
   - Else: parse via `_parse_chain(raw_chain)`.
   - If final `chain` is empty: raise `ValueError` as a defensive check.
   - Return `EnrichmentConfig` instance populated with all scalars and the parsed chain.

### 2.2 `tests/test_enrichment_config.py`

Add pytest-based tests that do not touch the real workspace:

1. **`test_default_chain_when_no_toml`**
   - Use `tmp_path` as a fake repo root with no `llmc.toml`.
   - Call `load_enrichment_config(tmp_path, env={})`.
   - Assert:
     - `concurrency == 1`, `cooldown_seconds == 0`
     - `est_tokens_per_span == 350`
     - `max_retries_per_span == 3`
     - Chain length is 2; both providers are `"ollama"`; models match `DEFAULT_7B_MODEL` and `DEFAULT_14B_MODEL`.

2. **`test_parse_chain_from_toml`**
   - Write a small `llmc.toml` with `[enrichment]` scalars and two `[[enrichment.chain]]` entries (one `ollama`, one `gateway`).
   - Call `load_enrichment_config` with empty `env` mapping.
   - Assert scalars match TOML values, including `est_tokens_per_span`, `default_tier`, `fallback_tier`.
   - Assert chain length is 2 and that name/provider/model fields match the TOML content.

3. **`test_env_overrides_toml_scalars`**
   - Write `llmc.toml` with `[enrichment]` scalar values and a single chain entry.
   - Pass `env` mapping with:
     - `ENRICH_CONCURRENCY`
     - `ENRICH_COOLDOWN_SECONDS`
     - `ENRICH_BATCH_SIZE`
     - `ENRICH_MAX_RETRIES`
   - Assert returned config uses env values for those scalars but keeps `est_tokens_per_span` from TOML.

4. **`test_enrich_chain_json_override`**
   - Write a TOML `enrichment.chain` entry.
   - Pass `env` mapping with `ENRICH_CHAIN_JSON` defining exactly one backend.
   - Assert chain length is 1 and values come from JSON, not TOML.

5. **`test_invalid_provider_raises`**
   - Write `llmc.toml` with a chain entry where `provider = "foo"`.
   - Assert `load_enrichment_config` raises `ValueError` and that the message mentions `provider` and `"foo"`.

## 3. Risks & Mitigations

- **Risk:** Misconfigured chain causes runtime failures.
  - **Mitigation:** Validate shape and providers up-front, fail fast with clear error messages.
- **Risk:** Silent divergence between script defaults and config defaults.
  - **Mitigation:** Centralize default model names and scalar defaults here; subsequent patches should remove the duplicated constants from `qwen_enrich_batch.py` and import them from this module instead.

## 4. Rollout Notes

- This patch is safe to merge in isolation: no existing callers are changed yet.
- Future patches that wire `load_enrichment_config` into `qwen_enrich_batch.py` and the daemon should be small and can reuse these tests by adding integration coverage.
