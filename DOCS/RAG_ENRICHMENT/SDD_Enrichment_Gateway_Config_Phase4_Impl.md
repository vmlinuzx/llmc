# Implementation Notes – Phase 4 Gateway / Gemini Config Wiring

This document explains exactly what changed in `scripts/qwen_enrich_batch.py`
to wire gateway behaviour into the enrichment config.

## 1. Files Touched

- `scripts/qwen_enrich_batch.py` (single file)

## 2. New locals around the main call

Inside the `while attempt_idx < max_attempts:` loop, just before the
existing `try: stdout, meta = call_qwen(...)` block, we introduce two
locals and a small config lookup:

```python
sampler: _GpuSampler | None = None
if _should_sample_local_gpu(selected_backend, host_url):
    sampler = _GpuSampler()
    sampler.start()
attempt_start = time.monotonic()
gateway_model_env_changed = False
gateway_model_prev: str | None = None
if (
    enrichment_cfg is not None
    and getattr(enrichment_cfg, "chain", None)
    and selected_backend == "gateway"
):
    gateway_cfg = _select_backend_config_for_tier(
        enrichment_cfg.chain,
        tier_for_attempt,
        provider="gemini",
    )
    if gateway_cfg is None:
        gateway_cfg = _select_backend_config_for_tier(
            enrichment_cfg.chain,
            tier_for_attempt,
            provider="gateway",
        )
    if gateway_cfg is not None and getattr(gateway_cfg, "model", None):
        gateway_model_prev = os.environ.get("GEMINI_MODEL")
        os.environ["GEMINI_MODEL"] = gateway_cfg.model  # type: ignore[assignment]
        gateway_model_env_changed = True
try:
    stdout, meta = call_qwen(...)
except RuntimeError as exc:
    ...
```

- `gateway_model_env_changed` tracks whether we modified the env.
- `gateway_model_prev` stores the prior value (if any) so we can restore
  it later.
- `_select_backend_config_for_tier` is reused, so no new helpers are
  required.

## 3. try/except → try/except/finally

The existing `except RuntimeError as exc:` block is kept intact, but
we extend the construct with a `finally` clause that restores the
environment when necessary:

```python
except RuntimeError as exc:
    failure_info = ("runtime", exc, None)
    gpu_stats = sampler.stop() if sampler else _blank_gpu_stats()
    attempt_duration = time.monotonic() - attempt_start
    attempt_records.append(...)
    ...
    if attempt_idx < max_attempts:
        time.sleep(args.retry_wait)
        continue
    break
finally:
    if gateway_model_env_changed:
        if gateway_model_prev is None:
            os.environ.pop("GEMINI_MODEL", None)
        else:
            os.environ["GEMINI_MODEL"] = gateway_model_prev
```

The following lines remain unchanged:

```python
gpu_stats = sampler.stop() if sampler else _blank_gpu_stats()
attempt_duration = time.monotonic() - attempt_start
result, failure = parse_and_validate(stdout, item, meta)
...
```

This ensures:

- Gateway config integration has **no effect** on parse/validation logic.
- GPU sampling and attempt logging continue to work as before.

## 4. Interaction with config_enrichment

This patch assumes that:

- `enrichment_cfg = load_enrichment_config(repo_root)` already ran.
- `enrichment_cfg.chain` is a list of `BackendConfig` instances, either
  from TOML/env or from the implicit default chain.

Gateway lookups happen only when:

```python
enrichment_cfg is not None
getattr(enrichment_cfg, "chain", None) is truthy
selected_backend == "gateway"
```

i.e. when:

- The user has requested the gateway backend (or `--api` implies it).
- The config loader succeeded.

## 5. Manual Sanity Checks

After applying the patch:

1. Run with no gateway entries:

   ```bash
   python3 scripts/qwen_enrich_batch.py --dry-run --router off --backend gateway
   ```

   - Behaviour should match pre‑patch: the model is driven by the
     environment or defaults.

2. Add a gateway entry into `llmc.toml`:

   ```toml
   [[enrichment.chain]]
   name = "gemini-fast"
   provider = "gemini"
   tier = "nano"
   model = "gemini-2.5-flash"
   ```

   - Run with `--backend gateway --router off --dry-run --verbose`.
   - Observe in logs / metrics that:
     - `meta["model"]` for gateway calls is `"gemini-2.5-flash"`.
     - Other tiers (7B/14B) are unaffected.

3. Add a second entry with `provider="gateway"` and a different model:

   - Confirm that if the first is deleted or mis‑tiered, the fallback
     entry is used.

## 6. Notes for Future Phases

- A future phase could reuse the same `_select_backend_config_for_tier`
  helper to build a full `BackendCascade` of multiple gateway and/or
  Ollama backends per span.
- This patch keeps behaviour surgical and backwards‑compatible while
  still moving gateway behaviour under the control of `llmc.toml`.
