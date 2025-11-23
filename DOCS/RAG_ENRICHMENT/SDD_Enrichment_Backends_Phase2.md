# SDD – Phase 2: Concrete Enrichment Backends (Ollama + Gateway)

## 1. Overview

Phase 2 introduces **concrete backend adapters** for the enrichment system,
implemented inside `scripts/qwen_enrich_batch.py` and backed by the generic
abstractions from Phase 1 (`tools.rag.enrichment_backends`).

This phase:

- Adds `BackendError`, `BackendAdapter`, `BackendCascade`, and `AttemptRecord`
  import into `scripts/qwen_enrich_batch.py`.
- Defines `_AdapterConfigShim`, `_OllamaBackendAdapter`, and
  `_GatewayBackendAdapter` in `scripts/qwen_enrich_batch.py`.
- Adds unit tests for these adapters under `tests/test_enrichment_adapters.py`.
- **Does not yet change** the main per-span enrichment loop; behaviour of
  `qwen_enrich_batch.py` for real runs remains unchanged.

These adapters will be used in later phases to build a configurable failover
chain of models/backends.

## 2. Goals

- Wrap existing `call_qwen` + `parse_and_validate` behaviour behind reusable
  adapters for Ollama and gateway/Gemini.
- Provide a clean place to merge:
  - Preset settings from `PRESET_CACHE` (model, options, keep_alive).
  - Future per-backend config overrides (model, options, URL, etc.).
- Map failures into `BackendError` with standardized `failure_type` and payload.
- Keep router and retry policy **unchanged** for now.

## 3. Design

### 3.1 AdapterConfigShim

A small dataclass used as a stand-in when no real backend config object is
available:

```python
@dataclass
class _AdapterConfigShim:
    name: str
    provider: str
    model: str | None = None
    tier: str | None = None
    url: str | None = None
    options: Dict[str, Any] | None = None
    keep_alive: str | float | int | None = None
```

This allows adapters to always expose a `.config` with the fields we care about
(name, provider, model, tier, url, options, keep_alive) without importing the
concrete enrichment config schema.

### 3.2 _OllamaBackendAdapter

Responsibilities:

- Accept a config object (or `None`) plus a `tier_preset` dict from
  `PRESET_CACHE["7b"]` or `PRESET_CACHE["14b"]`.
- Merge options according to the following precedence:
  - Start from tier preset: `model`, `options`, `keep_alive`.
  - If the config has matching attributes (`model`, `options`, `keep_alive`),
    they override the preset.
- Invoke `call_qwen` with:

  - `backend="ollama"`.
  - Preserved CLI args: `verbose`, `retries`, `retry_wait`, `gateway_path`,
    `gateway_timeout`.
  - Tier-specific `model_override`, `ollama_options`, `keep_alive`.
  - Host details: `ollama_base_url`, `ollama_host_label`.

- Run `parse_and_validate(stdout, item, meta)`.
- On success:

  - Ensure `meta["model"]` is set if `model_override` is known.
  - Set sensible defaults: `meta.setdefault("backend", "ollama")`,
    `meta.setdefault("host", host_label_or_url)`.
  - Return `(result, meta)`.

- On failure:

  - If `parse_and_validate` returns `failure=(kind, detail, payload)`, raise
    `BackendError` with `failure_type=kind` and `failure=failure`.
  - If it returns no failure tuple, treat it as `"runtime"`.

### 3.3 _GatewayBackendAdapter

Responsibilities:

- Wrap `call_qwen` with `backend="gateway"`.
- Optionally override the `GEMINI_MODEL` environment variable for the duration
  of the call:

  - If `config.model` is a non-empty string, temporarily set
    `os.environ["GEMINI_MODEL"] = config.model`.
  - Restore the previous value (or delete the variable) in a `finally` block.

- Run `parse_and_validate(stdout, item, meta)`.
- On success:

  - Ensure `meta["model"]` is set to `config.model` if not already present.
  - Default `meta["backend"]` to `"gateway"`.
  - Return `(result, meta)`.

- On failure:

  - Behave like `_OllamaBackendAdapter`, raising `BackendError` with
    `failure_type` and the failure payload.

### 3.4 Integration in qwen_enrich_batch.py

This phase does **not** change the main enrichment loop. The new classes are
defined but not yet wired into the per-span attempt/retry logic.

In a later phase, the loop will be refactored to:

- Construct one or more adapters per attempt.
- Use `BackendCascade` to try them in order.
- Use the existing router policy + size/validation thresholds to decide when to
  promote tiers or advance to the next backend/host.

## 4. File-Level Changes

### 4.1 scripts/qwen_enrich_batch.py

- New import near the top:

  ```python
  from tools.rag.enrichment_backends import BackendError, BackendAdapter, BackendCascade, AttemptRecord
  ```

- New definitions inserted between `call_qwen` and `extract_json`:

  - `_AdapterConfigShim`
  - `_OllamaBackendAdapter`
  - `_GatewayBackendAdapter`

These classes currently depend only on:

- `Path`, `argparse.Namespace`, `Dict`, `Any`.
- `call_qwen`, `parse_and_validate`.
- Environment variables for gateway (`GEMINI_MODEL`).
- Tier presets via `PRESET_CACHE` (passed in later; in this phase tests inject
  simple presets directly).

### 4.2 tests/test_enrichment_adapters.py

- New test module that exercises the adapters in isolation via monkeypatching:

  - `test_ollama_adapter_success`

    - Patches `call_qwen` and `parse_and_validate` to simulate a successful
      Ollama call.
    - Asserts that:
      - The adapter passes expected arguments to `call_qwen`.
      - `meta["backend"] == "ollama"`.
      - `meta["host"]` equals the host label.
      - Config `model` overrides the preset model for `meta["model"]`.

  - `test_ollama_adapter_validation_failure`

    - Patches `parse_and_validate` to return a `("validation", ...)` failure.
    - Asserts that the adapter raises `BackendError` with
      `failure_type == "validation"` and the original failure tuple preserved.

  - `test_gateway_adapter_success_respects_model_and_restores_env`

    - Uses `monkeypatch.setenv("GEMINI_MODEL", "orig-model")`.
    - Patches `call_qwen` to assert that during the call,
      `GEMINI_MODEL == "gemini-2.5-flash"`.
    - Patches `parse_and_validate` to simulate success.
    - Asserts that:
      - `meta["backend"] == "gateway"`.
      - `meta["model"] == "gemini-2.5-flash"`.
      - After the call, `GEMINI_MODEL` is restored to `"orig-model"`.

  - `test_gateway_adapter_validation_failure`

    - Patches `parse_and_validate` to return a validation failure.
    - Asserts `BackendError` with `failure_type == "validation"`.

## 5. Testing Strategy

- Unit tests:

  ```bash
  pytest tests/test_enrichment_backends.py tests/test_enrichment_adapters.py
  ```

- There are no integration changes in this phase; running the full test suite
  should behave as before.

## 6. Future Phases

- Phase 3 will refactor the per-span attempt loop in `qwen_enrich_batch.py` to
  construct one or more adapters per attempt and drive them via
  `BackendCascade.generate_for_span`.
- Later phases will use the enrichment config (`llmc.toml` / env overrides) to
  build a configurable chain of adapters that provides model/back-end failover.
