# SDD – Enrichment Config Tier Overrides (Phase 3)

## 1. Overview

This phase tightens the connection between the enrichment configuration
(`llmc.toml` / `load_enrichment_config`) and the enrichment runner
(`scripts/qwen_enrich_batch.py`) without changing the overall control
flow or retry semantics.

Goals:

- Let **llmc.toml** drive default batch size, cooldown, and retries
  when the user does not override them on the CLI.
- Allow the `[enrichment.chain]` entries (especially `provider=ollama`)
  to override **model**, **options**, **keep_alive**, and **base URL**
  for the 7B/14B tiers, instead of hard-wiring these values in the
  Python script or preset YAML.
- Keep behaviour backwards‑compatible when `llmc.toml` is absent or
  incomplete.

This is an incremental step toward a fully chain‑driven backend cascade,
but it already removes a large chunk of hidden defaults from the code.

## 2. Scope

**Modified**

- `scripts/qwen_enrich_batch.py`

**Unchanged (but relied on)**

- `tools/rag/config_enrichment.py`
  - `BackendConfig`
  - `EnrichmentConfig`
  - `load_enrichment_config`
  - implicit default 7B / 14B chain

No new modules or tests are introduced in this patch; it is intended to
be a small, low‑risk behavioural improvement to Phase 1/2.

## 3. Design

### 3.1 Config‑driven CLI defaults

After parsing CLI arguments and loading router policy, we already call
`load_enrichment_config(repo_root)`.

We now extend that block so that when `enrichment_cfg` is available, it
can influence runtime defaults:

- If the user did **not** override `--batch-size` (i.e. it is still `5`),
  we replace it with `enrichment_cfg.batch_size`.
- If the user did **not** override `--cooldown` (still `0`), we replace it
  with `enrichment_cfg.cooldown_seconds`.
- If the user did **not** override `--retries` (still `3`), we replace it
  with `enrichment_cfg.max_retries_per_span`.

Explicit CLI flags remain highest‑priority; config only fills in the
defaults.

### 3.2 Tier → BackendConfig selection helper

We introduce a small helper near the Ollama host utilities:

```python
def _select_backend_config_for_tier(chain, tier, provider: str = "ollama"):
    ...
```

Behaviour:

- Returns the first entry whose `provider` matches and whose `tier`
  matches `tier` (case‑insensitive).
- If no exact tier match is found, returns the first entry whose
  `provider` matches.
- Returns `None` if the chain is empty or no suitable entry exists.

The helper is intentionally untyped here to avoid a hard import dependency
on `BackendConfig` inside this script; it relies only on duck‑typed
attributes (`provider`, `tier`, `model`, `options`, `keep_alive`, `url`).

### 3.3 Using config to override Ollama 7B/14B presets

Inside the main enrichment loop, we keep the existing tier + preset
logic:

- `tier_for_attempt` is chosen based on router + policy.
- `preset_key` is `"7b"` or `"14b"`; `tier_preset` is pulled from
  `PRESET_CACHE`.
- `options`, `keep_alive`, and `tier_model_override` are initialised
  from `tier_preset` when `selected_backend == "ollama"`.

We then layer config on top:

- When `enrichment_cfg` is present and has a `chain`, and the
  `selected_backend` is `"ollama"`, we call:

  ```python
  backend_cfg = _select_backend_config_for_tier(
      enrichment_cfg.chain,
      tier_for_attempt,
      provider="ollama",
  )
  ```

- If `backend_cfg` is not `None`:
  - If `backend_cfg.options` is present, we **shallow‑copy** it into
    `options` so downstream tweaks can’t mutate the config object.
  - If `backend_cfg.keep_alive` is set, we use it in place of the
    preset value.
  - If `backend_cfg.model` is set, we override `tier_model_override`.
  - If `backend_cfg.url` is set, we record it as `backend_url_override`.

Host URL resolution is then updated:

- We initialise `host_label = None` and `host_url = backend_url_override`.
- If `selected_backend == "ollama"` and `host_url` is still falsey but
  `ollama_host_chain` is non‑empty, we fall back to the existing host
  chain logic:

  ```python
  host_entry = ollama_host_chain[min(current_host_idx, host_chain_count - 1)]
  host_label = host_entry.get("label")
  host_url = host_entry.get("url")
  ```

That means:

- For the **implicit default chain** built by `config_enrichment`, the
  tier → model mapping now flows from `BackendConfig` instead of being
  duplicated in the script.
- When the user defines an explicit `[enrichment.chain]` with
  `provider="ollama"` entries, those entries completely control the
  model name, options, keep‑alive, and base URL used when calling
  `call_qwen` for the 7B/14B tiers.

### 3.4 Backwards compatibility

- If `load_enrichment_config` fails, we log a verbose message and fall
  back to router defaults and CLI values (unchanged from Phase 2).
- If `enrichment_cfg` has no `chain` or the helper cannot find a matching
  entry for the requested tier/provider, we **do not** change the previous
  behaviour – presets and Ollama host chain are used as before.
- Gateway / API behaviour is unaffected in this patch; tier `"nano"`
  still maps to `backend_choice = "gateway"` and relies on existing
  gateway configuration.

## 4. Data / Control Flow Impact

- All changes are **local to `qwen_enrich_batch.py`**.
- There is no new IO, no DB schema changes, and no change to the
  enrichment JSON schema.
- The only side‑effects are:
  - Configuration now influences batch size / cooldown / retries.
  - Ollama model / options / keep‑alive / URL are now taken from
    `[enrichment.chain]` when available.

## 5. Risks & Mitigations

- **Risk:** Misconfigured `llmc.toml` could cause confusing runtime
  behaviour (e.g., invalid URL or model name).
  - *Mitigation:* Any `ValueError` from `load_enrichment_config` is
    logged when `--verbose` is enabled, and we fall back to known
    defaults.
- **Risk:** Subtle change in which model actually runs for a given tier.
  - *Mitigation:* Default chain mirrors the previous hard‑coded defaults,
    and logs show the chain when `--verbose` is used.

## 6. Out of Scope

- No use of `BackendCascade` yet; backend failover is still handled by
  the existing per‑attempt logic and Ollama host rotation.
- No CLI changes or new flags.
- No Gemini / gateway model selection logic changes.
