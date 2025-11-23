# SDD – Enrichment Backend Cascade Integration (Phase 4)

**Status:** Draft – implementation in `scripts/qwen_enrich_batch.py`  
**Owner:** Dave / LLMC Core  
**Scope:** Wire the new enrichment backend abstraction (`BackendCascade` + adapters)
into the `qwen_enrich_batch` driver without changing external CLI behaviour.

---

## 1. Problem & Goals

The enrichment batch driver (`scripts/qwen_enrich_batch.py`) currently:

- Chooses a tier (`7b` vs `14b` vs `nano`) and backend (`ollama` vs `gateway`) per span.
- Calls `call_qwen(...)` directly.
- Runs `parse_and_validate(...)` on the stdout.
- Implements its own retry logic, router policy, and host fail‑over.

Phase 1–3 added:

- A generic enrichment backend module: `tools.rag.enrichment_backends` with:
  - `BackendAdapter` protocol.
  - `BackendCascade` coordinator.
  - `AttemptRecord` for metrics / debugging.
- Adapter shims for Ollama and gateway backends, so callers don’t need to know
  about `call_qwen()` or `parse_and_validate()` details.

**Goal of Phase 4:**

Replace the ad‑hoc “tier → backend → call_qwen → parse_and_validate” logic
inside `qwen_enrich_batch` with a call to `BackendCascade`, while preserving:

- The same CLI flags and defaults.
- The same router tier promotion and schema‑failure behaviour.
- The same host‑chain fail‑over semantics for Ollama.
- The same metrics/ledger outputs (plus some extra backend detail where useful).

No behavioural changes should be visible from the CLI other than more consistent
metadata in logs/metrics.

---

## 2. Functional Requirements

1. **Backend selection via cascade**
   - For each attempt, build a `BackendCascade` that wraps exactly one adapter:
     - `_OllamaBackendAdapter` when backend is Ollama.
     - `_GatewayBackendAdapter` when backend is gateway/nano.
   - The cascade is responsible for invoking `call_qwen` and running
     `parse_and_validate`.

2. **Preserve router behaviour**
   - Router policies (`policy_schema_threshold`, `policy_line_threshold`,
     `policy_max_retries`) must behave exactly as before:
     - Validation failures increment `schema_failures`.
     - Repeated validation failures may promote to the fallback tier.
     - Line‑based promotion and generic failure promotion stay unchanged.

3. **Preserve host‑chain behaviour**
   - Ollama host chain semantics must be identical:
     - Only after we are at the fallback tier or router is disabled
       do we move to the next host in the chain.
     - Host index resets when we move to a new span.

4. **Preserve metrics / ledger shape**
   - `attempt_records` still records, per attempt:
     - tier, duration, GPU metrics, success/failure flag, failure type,
       model, host, and options.
   - Final `meta` still carries:
     - `backend`, `model`, `host`, token counts, and gpu_stats.

5. **Error handling compatibility**
   - Runtime exceptions from `call_qwen` must still be treated as
     `("runtime", exc, None)` failures for router logic.
   - Parse/validation/truncation failures must still go through
     `classify_failure` and drive router + schema promotion as before.

---

## 3. High‑Level Design

### 3.1 New Imports & Helpers

- Add import in `scripts/qwen_enrich_batch.py`:

  - `from tools.rag.enrichment_backends import BackendError, BackendAdapter, BackendCascade, AttemptRecord`

- Add local adapter shims:

  - `_AdapterConfigShim` – light stand‑in for a backend config object.
  - `_OllamaBackendAdapter` – wraps `call_qwen(..., backend="ollama")`
    and `parse_and_validate`.
  - `_GatewayBackendAdapter` – wraps `call_qwen(..., backend="gateway")`
    and `parse_and_validate`, including temporary `GEMINI_MODEL` override.

- Add `_build_cascade_for_attempt(...)` helper:

  - Inputs:
    - `backend` (CLI argument, `"auto" | "ollama" | "gateway"`)
    - `tier_for_attempt` (`"7b" | "14b" | "nano"`)
    - `repo_root`, `args`
    - `ollama_host_chain`, `current_host_idx`, `host_chain_count`
  - Behaviour:
    - Mirrors existing tier/backend selection logic used in the main loop.
    - Resolves `preset_key` + `tier_preset` from `PRESET_CACHE`.
    - For Ollama:
      - Chooses host URL/label from `ollama_host_chain` using current host index.
      - Instantiates `_OllamaBackendAdapter` with that host + preset.
    - For gateway/nano:
      - Instantiates `_GatewayBackendAdapter`.
    - Returns:
      - `BackendCascade` instance
      - `preset_key`, `tier_preset`
      - `host_label`, `host_url`
      - `selected_backend`

### 3.2 Adapter Semantics

**_OllamaBackendAdapter**

- Resolves effective parameters per attempt:

  - Start with tier preset: `options`, `keep_alive`, `model`.
  - Allow config overrides (if present) for options/keep_alive/model.

- Calls `call_qwen` with:

  - `backend="ollama"`
  - Resolved `model_override`, `ollama_options`, `keep_alive`
  - `ollama_base_url` and `ollama_host_label` for metrics.

- On success:

  - Runs `parse_and_validate(stdout, item, meta)`.
  - If `result` is not `None`, ensures `meta` has:
    - `backend="ollama"`
    - `host` (host label/url)
    - `model` (if not already set).

- On failure:

  - If `failure` is `None`, raise `BackendError(failure_type="runtime")`.
  - If `failure` is a tuple `(kind, detail, payload)`, raise `BackendError`
    with `failure_type=kind` and `failure=tuple`.

**_GatewayBackendAdapter**

- Optionally overrides `GEMINI_MODEL` for the duration of the call based on
  a config/model override.
- Calls `call_qwen` with `backend="gateway"`.
- Mirrors the same success/failure mapping to `BackendError` as Ollama adapter.

### 3.3 Attempt Loop Integration

Inside the per‑span processing loop:

1. **Tier / backend selection**

   - Compute `tier_for_attempt = current_tier or start_tier`.
   - Append to `tiers_history`.
   - Call `_build_cascade_for_attempt(...)` to obtain:
     - `cascade`
     - `preset_key`, `tier_preset`
     - `host_label`, `host_url`
     - `selected_backend`

2. **Preset‑derived options**

   - Compute:
     - `options = tier_preset.get("options")` for Ollama; else `None`.
     - `keep_alive = tier_preset.get("keep_alive")` for Ollama; else `None`.
     - `tier_model_override = tier_preset.get("model")` for Ollama; else `None`.

3. **GPU sampling**

   - Start `_GpuSampler` when `_should_sample_local_gpu(selected_backend, host_url)`.

4. **Backend cascade call**

   - Measure `attempt_start = time.monotonic()`.
   - Call `cascade.generate_for_span(prompt, item=item)` inside a `try`.
   - On `BackendError as exc`:
     - Stop GPU sampler, compute `attempt_duration`.
     - Use `exc.failure` to distinguish runtime vs non‑runtime:
       - **Runtime (exc.failure is None):**
         - Set `failure_info = ("runtime", exc, None)`.
         - Append attempt record with failure `"runtime"`.
         - Apply router fallback tier and host‑chain rotation logic exactly
           as in the previous implementation.
       - **Non‑runtime (validation/parse/truncation):**
         - Set `failure_info = exc.failure`.
         - Compute `failure_type = classify_failure(failure_info)`.
         - Append attempt record with `failure_type`.
         - Increment `schema_failures` on `"validation"`.
         - Evaluate:
           - `promote_due_to_schema`
           - `promote_due_to_size`
           - `promote_due_to_failure`
         - Apply the same tier promotion, host fail‑over, and retry logic
           as before.
     - `break` once we’ve exhausted attempts for this span.

5. **Success path**

   - On success, stop GPU sampler and compute `attempt_duration`.
   - Set `success = True`, `final_result = result`.
   - Build `final_meta = {**meta, "gpu_stats": ..., "options": options, "tier_key": preset_key}`.
   - Append a successful `attempt_record` including:
     - tier, duration, gpu_stats, success, options, model, host.
   - `break` out of the attempt loop.

6. **Post‑loop handling**

   - `router_tier = tiers_history[-1] if tiers_history else start_tier`
     continues to be used for router accounting.
   - On failure (`success is False`), `failure_info` is still passed into
     `handle_failure` to write a ledger entry and log diagnostics.

---

## 4. Data & Control Flows

### 4.1 Data

Per span:

- Inputs:
  - `item` – enrichment job row (file, span, config).
  - `prompt` – fully rendered enrichment prompt.
- Outputs:
  - `final_result` – validated enrichment payload written back to DB.
  - `final_meta` – metadata emitted for tokens, backend, GPU, etc.
  - `attempt_records` – internal attempts list summarised into metrics.

### 4.2 Control Flow Summary

1. Derive router + policy settings.
2. Enter attempt loop (bounded by `policy_max_retries`).
3. On each attempt:
   - Build cascade from tier/backend + host chain.
   - Call cascade; either get result or `BackendError`.
   - On failure, update router and host index and possibly retry.
4. On success, break and write success ledger.
5. On overall failure, call `handle_failure` with `failure_info` and write a
   failure ledger.

---

## 5. Backwards Compatibility / Migration

- No schema changes to the enrichment DB or ledger.
- No CLI changes or new flags.
- Existing scripts and TUI/CLI entrypoints continue to work as before.
- This change is a refactor of the call path, not of the public API surface.

Rollback path: restore the old `while attempt_idx < max_attempts:` block and
remove the `_build_cascade_for_attempt` helper and adapter classes.
