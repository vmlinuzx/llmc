# Implementation Notes – Phase 2 Concrete Adapters

## Files

- `scripts/qwen_enrich_batch.py`
  - New import for backend abstractions.
  - New internal classes:
    - `_AdapterConfigShim`
    - `_OllamaBackendAdapter`
    - `_GatewayBackendAdapter`
- `tests/test_enrichment_adapters.py`
  - New unit tests for adapter behaviour.

## Behaviour

- No changes are made to the main enrichment loop yet.
- Existing CLI flags, router policy, and DB updates are unaffected.
- The new adapters simply provide a clean, testable wrapper around
  `call_qwen` and `parse_and_validate`, ready to be used by a cascade in a
  future phase.

## Adapter Semantics Summary

- `_OllamaBackendAdapter`:
  - Merges tier presets from `PRESET_CACHE` with config overrides.
  - Calls `call_qwen(..., backend="ollama", ...)`.
  - Uses `parse_and_validate` and raises `BackendError` on parse/validation
    failures.

- `_GatewayBackendAdapter`:
  - Optionally overrides `GEMINI_MODEL` during the call based on `config.model`.
  - Calls `call_qwen(..., backend="gateway", ...)`.
  - Uses `parse_and_validate` and raises `BackendError` on failure.
  - Restores the original `GEMINI_MODEL` value afterwards.

These semantics are validated in isolation by the new tests.

## How This Enables Later Work

- With the adapters in place, future phases can:
  - Build a list of adapters for each attempt (e.g., multiple Ollama hosts,
    followed by a gateway adapter).
  - Use `BackendCascade` to try them in order.
  - Record rich attempt metadata via `AttemptRecord` for metrics and logging.

At that point, model/back-end failover becomes a matter of config + ordering,
rather than ad-hoc conditional logic in the enrichment loop.
