# SDD – Phase 4: Gateway / Gemini Enrichment Config Wiring

## 1. Overview

This phase extends the enrichment configuration so that **gateway / Gemini
calls are driven by `llmc.toml`**, not by ad‑hoc environment variables
scattered around the shell.

Concretely:

- For `selected_backend == "gateway"` in `scripts/qwen_enrich_batch.py`,
  we now consult `EnrichmentConfig.chain` for a matching backend entry
  and set the `GEMINI_MODEL` environment variable just for the duration
  of that attempt.
- This lets you specify the gateway model (e.g. `gemini-2.5-flash`) in
  `llmc.toml` alongside your Ollama chain, and have the enrichment runner
  respect it without touching shell scripts or wrapper env.
- Existing error handling, router tier logic, and retries are preserved.

This does **not** yet introduce a full multi-backend cascade per span.
It is a targeted wiring step to make gateway behaviour consistent with
the config-driven approach we already applied to Ollama tiers.

## 2. Scope

**Modified**

- `scripts/qwen_enrich_batch.py`

**Unchanged (but relied on)**

- `tools/rag/config_enrichment.py`
  - `EnrichmentConfig`
  - `BackendConfig`
  - `load_enrichment_config`
  - Chain parsing & validation

## 3. Design

### 3.1 Gateway model selection via config

We reuse the existing helper:

```python
def _select_backend_config_for_tier(chain, tier, provider: str = "ollama"):
    ...
```

For gateway calls we invoke it with a different provider value:

1. Primary lookup: `provider="gemini"`
2. Fallback lookup: `provider="gateway"`

This lets you use either:

```toml
[[enrichment.chain]]
name = "gemini-fast"
provider = "gemini"
tier = "nano"
model = "gemini-2.5-flash"
```

or a more generic:

```toml
[[enrichment.chain]]
name = "gateway-fast"
provider = "gateway"
tier = "nano"
model = "gemini-2.5-flash"
```

In both cases, the entry can be selected for `tier_for_attempt == "nano"`
(or any other tier if you choose to tag it differently).

### 3.2 Environment handling

`call_via_gateway` currently reads `GEMINI_MODEL` from the environment:

```python
model_label = meta.get("model") or (
    env.get("AZURE_OPENAI_DEPLOYMENT")
    if azure_env_available(env)
    else env.get("GEMINI_MODEL", "gemini")
)
```

Instead of asking users to export `GEMINI_MODEL` manually, we now manage
it around each gateway attempt:

- Right before calling `call_qwen` we do:

  ```python
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
          os.environ["GEMINI_MODEL"] = gateway_cfg.model
          gateway_model_env_changed = True
  ```

- We wrap the existing `call_qwen` invocation in a `try/except/finally`:

  ```python
  try:
      stdout, meta = call_qwen(...)
  except RuntimeError as exc:
      # existing runtime handling
      ...
  finally:
      if gateway_model_env_changed:
          if gateway_model_prev is None:
              os.environ.pop("GEMINI_MODEL", None)
          else:
              os.environ["GEMINI_MODEL"] = gateway_model_prev
  ```

- This guarantees that:
  - The configured gateway model is applied for that attempt only.
  - The environment is restored afterwards (no polluted process‑wide
    state, no surprises for later calls).

### 3.3 Interaction with tiers and router

- The router still controls `tier_for_attempt` (e.g. `"nano"`).
- The same `tier_for_attempt` is passed into
  `_select_backend_config_for_tier(chain, tier_for_attempt, provider=...)`
  so you can keep gateway entries tier-specific if you want.
- If no matching config entry exists for `provider in {"gemini","gateway"}`,
  nothing changes: we fall back to the legacy behaviour where
  `GEMINI_MODEL` is whatever the shell/env says (or `"gemini"`).
- Ollama tier logic, options, keep-alive, and host rotation are
  unchanged from Phase 3.

## 4. Config Examples

### 4.1 Local 7B/14B with Gemini fallback

```toml
[enrichment]
default_tier = "7b"
fallback_tier = "14b"

[[enrichment.chain]]
name = "athena-7b"
provider = "ollama"
tier = "7b"
url = "http://athena:11434"
model = "qwen2.5:7b-instruct-q4_K_M"

[[enrichment.chain]]
name = "athena-14b"
provider = "ollama"
tier = "14b"
url = "http://athena:11434"
model = "qwen2.5:14b-instruct-q4_K_M"

[[enrichment.chain]]
name = "gemini-fast"
provider = "gemini"
tier = "nano"
model = "gemini-2.5-flash"
```

Behaviour:

- 7B / 14B tiers behave as in Phase 3 (config‑driven Ollama).
- For `"nano"` tier (gateway), the runner will temporarily set
  `GEMINI_MODEL=gemini-2.5-flash` for the duration of each gateway call.

### 4.2 Generic gateway provider

```toml
[[enrichment.chain]]
name = "gateway-default"
provider = "gateway"
tier = "nano"
model = "gemini-2.5-pro"
```

- If no `provider="gemini"` entry matches, the code falls back to
  `provider="gateway"`, so this entry will be used instead.

## 5. Behavioural Notes

- If `llmc.toml` does not define any gateway/gemini entries, behaviour
  is unchanged.
- If the configured model string is invalid for the gateway process,
  the call will fail as before; the existing `RuntimeError` path
  and router/host fallbacks still apply.
- The change is **per attempt**, not global:
  - Each attempt restores the previous `GEMINI_MODEL` value (or removes
    it entirely if it was not set).

## 6. Out of Scope

- Multi‑backend cascade per span (e.g. gemini‑fast → gemini‑pro → ollama)
  is not implemented in this phase.
- No new CLI flags are introduced.
- No changes to `tools/rag/enrichment_backends.py` – cascade remains
  available for future phases but is not wired into the main loop yet.
