# Implementation Notes – Enrichment Config Tier Overrides (Phase 3)

This document explains how the Phase 3 patch is implemented inside
`scripts/qwen_enrich_batch.py` so that a code agent (or human) can review
and reason about the changes quickly.

## 1. Files Touched

- `scripts/qwen_enrich_batch.py`

## 2. Helper: `_select_backend_config_for_tier`

Added just above `health_check_ollama_hosts`:

- Signature: `def _select_backend_config_for_tier(chain, tier, provider: str = "ollama")`
- Logic:
  - If `chain` is falsey → return `None`.
  - First pass: iterate entries, check
    `cfg.provider.lower() == provider.lower()` and
    `cfg.tier.lower() == tier.lower()`; return first match.
  - Second pass: return first entry whose provider matches.
  - If nothing matches, return `None`.

The function is intentionally untyped (`chain` is duck‑typed) to avoid a
hard import of `BackendConfig` in this script.

## 3. Enrichment config block

In `main()`, the existing block:

```python
router_enabled = ...
policy_settings = ...
policy_default_tier = ...
policy_fallback_tier = ...
# Optional: enrichment config...
enrichment_cfg = None
try:
    enrichment_cfg = load_enrichment_config(repo_root)
except ValueError as exc:
    ...
else:
    if enrichment_cfg.default_tier:
        ...
    if enrichment_cfg.fallback_tier:
        ...
    if args.verbose and enrichment_cfg.chain:
        ...
promote_cfg = policy_settings.get("promote_if", {}) or {}
```

is replaced with an extended version that keeps the above semantics and
adds scalar overrides:

```python
if enrichment_cfg.default_tier:
    policy_default_tier = enrichment_cfg.default_tier.lower()
if enrichment_cfg.fallback_tier:
    policy_fallback_tier = enrichment_cfg.fallback_tier.lower()

# Apply scalar overrides only when CLI left defaults in place.
if getattr(args, "batch_size", 5) == 5:
    args.batch_size = getattr(enrichment_cfg, "batch_size", args.batch_size)
if getattr(args, "cooldown", 0) == 0:
    args.cooldown = getattr(enrichment_cfg, "cooldown_seconds", args.cooldown)
if getattr(args, "retries", 3) == 3:
    args.retries = getattr(enrichment_cfg, "max_retries_per_span", args.retries)
```

The verbose chain logging is unchanged except for using `getattr` to
guard on `enrichment_cfg.chain` existing.

## 4. Ollama tier overrides in the main loop

Inside the `while attempt_idx < max_attempts:` loop, the backend selection
block is updated.

Previously:

```python
backend_choice = "gateway" if tier_for_attempt == "nano" else "ollama"
selected_backend = backend_choice if backend == "auto" else backend
preset_key = "14b" if tier_for_attempt == "14b" else "7b"
tier_preset = PRESET_CACHE.get(preset_key, PRESET_CACHE["7b"])
options = tier_preset.get("options") if selected_backend == "ollama" else None
keep_alive = tier_preset.get("keep_alive") if selected_backend == "ollama" else None
tier_model_override = tier_preset.get("model") if selected_backend == "ollama" else None
host_label = None
host_url = None
if selected_backend == "ollama" and ollama_host_chain:
    host_entry = ollama_host_chain[min(current_host_idx, host_chain_count - 1)]
    host_label = host_entry.get("label")
    host_url = host_entry.get("url")
```

Now:

```python
backend_choice = "gateway" if tier_for_attempt == "nano" else "ollama"
selected_backend = backend_choice if backend == "auto" else backend
preset_key = "14b" if tier_for_attempt == "14b" else "7b"
tier_preset = PRESET_CACHE.get(preset_key, PRESET_CACHE["7b"])
options = tier_preset.get("options") if selected_backend == "ollama" else None
keep_alive = tier_preset.get("keep_alive") if selected_backend == "ollama" else None
tier_model_override = tier_preset.get("model") if selected_backend == "ollama" else None
backend_url_override = None
if enrichment_cfg is not None and getattr(enrichment_cfg, "chain", None) and selected_backend == "ollama":
    backend_cfg = _select_backend_config_for_tier(
        enrichment_cfg.chain,
        tier_for_attempt,
        provider="ollama",
    )
    if backend_cfg is not None:
        cfg_options = getattr(backend_cfg, "options", None) or None
        if cfg_options is not None:
            options = dict(cfg_options)
        cfg_keep_alive = getattr(backend_cfg, "keep_alive", None)
        if cfg_keep_alive is not None:
            keep_alive = cfg_keep_alive
        cfg_model = getattr(backend_cfg, "model", None)
        if cfg_model:
            tier_model_override = cfg_model
        cfg_url = getattr(backend_cfg, "url", None)
        if cfg_url:
            backend_url_override = cfg_url
host_label = None
host_url = backend_url_override
if selected_backend == "ollama" and not host_url and ollama_host_chain:
    host_entry = ollama_host_chain[min(current_host_idx, host_chain_count - 1)]
    host_label = host_entry.get("label")
    host_url = host_entry.get("url")
```

The remaining logic for `_GpuSampler`, `call_qwen`, parse/validate,
router‑driven promotions, and Ollama host rotation is unchanged.

## 5. Behavioural Summary

- When a repository has a valid `llmc.toml` with an `[enrichment]` block:
  - Default batch size / cooldown / retries are taken from config unless
    the user overrides them on the CLI.
  - For `backend_choice == "ollama"` (7B / 14B tiers), we consult
    `enrichment_cfg.chain` to adjust model/options/keep_alive/url.
- When config is missing or invalid, the previous behaviour is preserved.

## 6. Manual Sanity Tests

After applying the patch, recommended quick checks:

1. Run with no `llmc.toml`:
   - Ensure behaviour matches previous defaults.
2. Add a minimal `llmc.toml`:

   ```toml
   [enrichment]
   batch_size = 3
   cooldown_seconds = 120
   max_retries_per_span = 4

   [[enrichment.chain]]
   name = "athena-7b"
   provider = "ollama"
   model = "qwen2.5:7b-instruct-q4_K_M"
   url = "http://athena:11434"
   tier = "7b"
   ```

   - Run `scripts/qwen_enrich_batch.py --dry-run --verbose` and confirm:
     - Log prints the enrichment chain.
     - The first loop uses `batch_size = 3` and `cooldown = 120`.
     - Invocations to Ollama are directed at `http://athena:11434`.
3. Override batch size explicitly:
   - Run with `--batch-size 10` and confirm the config batch size is
     ignored (CLI wins).
