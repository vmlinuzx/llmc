# SDD – Phase 3: Backend Cascade Builder Helper

## 1. Overview

Phase 3 introduces a **backend cascade builder helper** into
`scripts/qwen_enrich_batch.py` that mirrors the existing tier/back-end and
Ollama host selection logic, but returns a structured
`BackendCascade` + preset metadata which future phases can plug into the
main enrichment loop.

This phase is deliberately conservative:

- There is **no change** to the current enrichment loop behaviour.
- We add `_build_cascade_for_attempt(...)` as a small, test-backed helper.
- Later phases can use this helper to migrate from direct `call_qwen(...)`
  calls to a `BackendCascade`-driven flow without copy/pasting selection
  logic or re-implementing host/tier rules.

## 2. Goals

- Centralize how we derive:
  - Effective backend for a given attempt (`ollama` vs `gateway`).
  - Preset tier key (`7b` vs `14b`) and `PRESET_CACHE` lookup.
  - Ollama host label/URL for a given `current_host_idx`.
- Construct a `BackendCascade` with the correct adapter type:
  - `_OllamaBackendAdapter` when the effective backend is Ollama.
  - `_GatewayBackendAdapter` when the effective backend is gateway/nano.
- Provide a **single place** to evolve host/chain semantics in future
  (e.g. supporting multiple adapters per attempt) while keeping the rest of
  the enrichment logic focused on retry and policy decisions.

## 3. Design

### 3.1 Helper: `_build_cascade_for_attempt`

New function added just before `main()` in
`scripts/qwen_enrich_batch.py`:

```python
def _build_cascade_for_attempt(
    *,
    backend: str,
    tier_for_attempt: str,
    repo_root: Path,
    args: argparse.Namespace,
    ollama_host_chain: Sequence[Mapping[str, object]],
    current_host_idx: int,
    host_chain_count: int,
) -> tuple[BackendCascade, str, Dict[str, Any], str | None, str | None, str]:
    ...
```

Responsibilities:

1. **Backend selection**

   ```python
   backend_choice = "gateway" if tier_for_attempt == "nano" else "ollama"
   selected_backend = backend_choice if backend == "auto" else backend
   ```

   This matches the existing logic in `main()`: router tier `nano` implies
   a gateway backend, otherwise Ollama, unless the CLI forces a backend.

2. **Preset selection**

   ```python
   preset_key = "14b" if tier_for_attempt == "14b" else "7b"
   tier_preset = PRESET_CACHE.get(preset_key, PRESET_CACHE["7b"])
   ```

   The helper does not change `PRESET_CACHE` behaviour; it just centralizes
   its use for the cascade.

3. **Adapter construction**

   - If `selected_backend == "ollama"`:

     - Resolve host label/URL from `ollama_host_chain` using
       `current_host_idx` and `host_chain_count`.
     - Construct a single `_OllamaBackendAdapter` with:

       ```python
       _OllamaBackendAdapter(
           config=None,
           repo_root=repo_root,
           args=args,
           host_url=host_url or "http://localhost:11434",
           host_label=host_label,
           tier_preset=tier_preset,
           tier_for_attempt=tier_for_attempt,
       )
       ```

   - If `selected_backend in {"gateway", "nano"}`:

     - Construct a single `_GatewayBackendAdapter` with:

       ```python
       _GatewayBackendAdapter(
           config=None,
           repo_root=repo_root,
           args=args,
       )
       ```

   - Otherwise (unknown backend string):

     - Fall back to a single `_OllamaBackendAdapter` with a
       `http://localhost:11434` base URL.
     - Normalize `selected_backend = "ollama"` so callers can still
       reason about the effective backend.

4. **Return value**

   The helper returns a tuple:

   ```python
   (
       cascade,       # BackendCascade
       preset_key,    # "7b" or "14b"
       tier_preset,   # PRESET_CACHE[preset_key]
       host_label,    # str | None
       host_url,      # str | None
       selected_backend,  # effective backend string
   )
   ```

   This gives the caller everything it needs to:
   - Drive GPU sampling decisions (`_should_sample_local_gpu`).
   - Log host/model information.
   - Run `cascade.generate_for_span(...)` with the correct adapters.

### 3.2 No Behaviour Change (Yet)

- The existing `while attempt_idx < max_attempts:` loop in `main()` is
  left untouched in Phase 3.
- All real enrichment work still goes through:
  - `call_qwen(...)`
  - `parse_and_validate(...)`
  - Existing attempt/host/tier promotion logic.

This helper is an **internal building block** for the next phase, where
we will swap out the direct `call_qwen` calls for `BackendCascade` usage
while leaning on `_build_cascade_for_attempt` to keep tier/host logic
consistent.

## 4. File-Level Changes

### 4.1 scripts/qwen_enrich_batch.py

- New helper function `_build_cascade_for_attempt(...)` inserted directly
  above `def main() -> int:`.
- No other changes to the file in this phase.

### 4.2 tests/test_enrichment_cascade_builder.py

New test module verifying the helper behaviour via monkeypatching:

- `test_build_cascade_for_ollama_backend`

  - Patches `PRESET_CACHE` to a small deterministic dict.
  - Patches `_OllamaBackendAdapter` and `_GatewayBackendAdapter` with thin
    fake classes recording their inputs.
  - Calls `_build_cascade_for_attempt` with:

    ```python
    backend="auto"
    tier_for_attempt="7b"
    ollama_host_chain=[{"label": "athena", "url": "http://athena:11434"}, ...]
    current_host_idx=0
    host_chain_count=len(ollama_hosts)
    ```

  - Asserts:

    - Returned object is a `BackendCascade` with exactly one backend.
    - Backend is an instance of `_FakeOllamaAdapter`.
    - `preset_key == "7b"` and `tier_preset["model"] == "m7"`.
    - `host_label` / `host_url` match the first host.
    - The fake adapter saw the same host label/URL.
    - `selected_backend == "ollama"`.

- `test_build_cascade_for_gateway_backend`

  - Forces `backend="gateway", tier_for_attempt="nano"`.
  - Asserts:

    - Cascade contains `_FakeGatewayAdapter`.
    - `preset_key` falls back to `"7b"` with model `"m7"`.
    - `host_label` / `host_url` are `None`.
    - `selected_backend` is `"gateway"` or `"nano"`.

- `test_build_cascade_for_unknown_backend_falls_back_to_ollama`

  - Uses `backend="weird"` to simulate an unexpected backend string.
  - Asserts cascade uses `_FakeOllamaAdapter` and `selected_backend` is
    normalized to `"ollama"`.

## 5. Testing Strategy

- Run only the new helper-level tests, plus the existing backend tests:

  ```bash
  pytest tests/test_enrichment_backends.py          tests/test_enrichment_adapters.py          tests/test_enrichment_cascade_builder.py
  ```

- Full-suite runs should continue to behave exactly as they did after
  Phase 2; this phase is behaviour-neutral.

## 6. Future Phases

- Next phase will **replace the inner per-attempt logic** in `main()` with
  calls to `_build_cascade_for_attempt` + `BackendCascade.generate_for_span`,
  using the adapters introduced in Phase 2.
- Once that is stable, we can plug in the enrichment config (TOML/env) to
  build richer chains (multiple hosts, explicit gateway fallback, etc.)
  without touching the core retry/promotion policy again.
