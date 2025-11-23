# Implementation SDD – Enrichment Backend Cascade Integration (Phase 4)

**Status:** Implemented in patch – ready for review  
**Target files:**
- `scripts/qwen_enrich_batch.py`
- `tools/rag/enrichment_backends.py` (new in Phase 1, bundled again here)
- `tests/test_enrichment_backends.py`

---

## 1. File‑level Changes

### 1.1 `scripts/qwen_enrich_batch.py`

1. **New imports** (near the other top‑level imports):

   - `from tools.rag.enrichment_backends import BackendError, BackendAdapter, BackendCascade, AttemptRecord`

2. **New adapter shims** (inserted between `call_qwen` and `extract_json`):

   - `_AdapterConfigShim`
   - `_OllamaBackendAdapter`
   - `_GatewayBackendAdapter`

   These encapsulate the per‑backend wiring (`call_qwen` + `parse_and_validate`)
   but do not change how prompts are built or how failures are classified.

3. **New helper `_build_cascade_for_attempt(...)`** (inserted just before `def main()`):

   - Mirrors the old tier/backend/host selection logic from the main attempt
     loop.
   - Returns `(cascade, preset_key, tier_preset, host_label, host_url, selected_backend)`.

4. **Refactored attempt loop** inside `main()`:

   - Replaces the `while attempt_idx < max_attempts:` block that:
     - Picked a backend.
     - Called `call_qwen` directly.
     - Ran `parse_and_validate` inline.

   With a new loop that:

   ```python
   while attempt_idx < max_attempts:
       attempt_idx += 1
       tier_for_attempt = current_tier or start_tier
       tiers_history.append(tier_for_attempt)

       cascade, preset_key, tier_preset, host_label, host_url, selected_backend = _build_cascade_for_attempt(
           backend=backend,
           tier_for_attempt=tier_for_attempt,
           repo_root=repo_root,
           args=args,
           ollama_host_chain=ollama_host_chain,
           current_host_idx=current_host_idx,
           host_chain_count=host_chain_count,
       )

       options = tier_preset.get("options") if selected_backend == "ollama" else None
       keep_alive = tier_preset.get("keep_alive") if selected_backend == "ollama" else None
       tier_model_override = tier_preset.get("model") if selected_backend == "ollama" else None

       sampler: _GpuSampler | None = None
       if _should_sample_local_gpu(selected_backend, host_url):
           sampler = _GpuSampler()
           sampler.start()
       attempt_start = time.monotonic()
       try:
           result, meta, backend_attempts = cascade.generate_for_span(
               prompt,
               item=item,
           )
       except BackendError as exc:
           gpu_stats = sampler.stop() if sampler else _blank_gpu_stats()
           attempt_duration = time.monotonic() - attempt_start
           # runtime vs non‑runtime branches (see below)
           ...
       else:
           gpu_stats = sampler.stop() if sampler else _blank_gpu_stats()
           attempt_duration = time.monotonic() - attempt_start
           success = True
           final_result = result
           final_meta = {**meta, "gpu_stats": gpu_stats, "options": options, "tier_key": preset_key}
           attempt_records.append(...)
           break
   ```

   **Runtime branch (`exc.failure is None`)**

   - Treat as pure runtime failure:

     ```python
     failure_info = ("runtime", exc, None)
     attempt_records.append({..., "failure": "runtime"})
     ```

   - Apply router fallback:

     - If router enabled and not already at fallback tier:
       - `current_tier = policy_fallback_tier` and `continue`.
     - Else if Ollama and either router disabled or at fallback tier:
       - Move to next host in `ollama_host_chain`, reset `current_tier` to `start_tier`.
     - Else, if attempts remain:
       - Sleep and retry.
     - Otherwise, `break`.

   **Non‑runtime branch (`exc.failure is not None`)**

   - Extract failure tuple and classify:

     ```python
     failure_info = exc.failure
     failure_type = classify_failure(failure_info)
     last_attempt = exc.attempts[-1] if exc.attempts else None
     ```

   - Append attempt record with `failure_type`, model, and host from `last_attempt`
     (falling back to tier preset / host label if needed).
   - Increment `schema_failures` when `failure_type == "validation"`.
   - Compute:

     ```python
     promote_due_to_schema = (
         schema_failures >= policy_schema_threshold and tier_for_attempt != policy_fallback_tier
     )
     promote_due_to_size = (
         router_enabled and line_count >= policy_line_threshold and tier_for_attempt != policy_fallback_tier
     )
     promote_due_to_failure = (
         router_enabled
         and failure_type in {"runtime", "parse", "truncation"}
         and tier_for_attempt != policy_fallback_tier
     )
     ```

   - Apply promotions / host‑failover / retries using the same structure as the
     previous implementation.

### 1.2 `tools/rag/enrichment_backends.py` (from Phase 1)

- Defines:
  - `BackendAdapter` protocol.
  - `AttemptRecord` dataclass.
  - `BackendError` exception type.
  - `BackendCascade` class with `generate_for_span(...)` that:
    - Iterates through a list of adapters.
    - Tracks attempts and wraps the last error into a `BackendError` if all fail.

No changes were required for Phase 4; we simply rely on its public API.

### 1.3 `tests/test_enrichment_backends.py` (from Phase 1)

- Provides unit coverage for `BackendCascade` behaviour:
  - Success on first adapter.
  - Success on fallback adapter after the first fails.
  - Error reporting and attempts list on total failure.

Phase 4 does not add new tests, but continues to rely on this coverage.

---

## 2. Behavioural Checks

**What should remain the same:**

- CLI flags and defaults for `qwen_enrich_batch`.
- How many attempts are made per span given the same policy.
- When and how the router promotes from `7b` to `14b`.
- When Ollama host fail‑over occurs.
- The ledger records for success/failure, apart from the internal
  `attempt_records` details.

**What is improved:**

- All backend execution now flows through `BackendCascade` which:
  - Normalises attempt recording.
  - Carries structured `AttemptRecord` data for future debugging and metrics.
- `qwen_enrich_batch` no longer needs to know about gateway vs Ollama details
  beyond choosing which adapter to build.

---

## 3. Testing Plan

1. **Unit tests**

   - `python -m pytest tests/test_enrichment_backends.py`

2. **Targeted smoke tests** (from repo root)

   - Run the enrichment batch against a small sample repo with Ollama:

     ```bash
     python scripts/qwen_enrich_batch.py        --backend ollama        --repo-path /path/to/sample/repo        --max-items 3        --verbose
     ```

   - Repeat using the gateway backend (Gemini) if configured:

     ```bash
     GEMINI_MODEL=gemini-2.0-pro      python scripts/qwen_enrich_batch.py        --backend gateway        --repo-path /path/to/sample/repo        --max-items 3        --verbose
     ```

   - Observe:
     - Attempts still route through the correct tiers and hosts.
     - Failures still promote as expected.

3. **Regression via your existing LLMC test harness**

   - Run the existing enrichment / RAG end‑to‑end tests that depend on
     `qwen_enrich_batch`.  
   - Confirm no behavioural regressions in:
     - Enrichment DB contents.
     - Token accounting / GPU stats fields.
     - Router tier / host selection outputs.

---

## 4. Rollback

To revert Phase 4 only:

1. Restore the previous `while attempt_idx < max_attempts:` loop from
   `scripts/qwen_enrich_batch.py` (pre‑cascade version).
2. Remove `_build_cascade_for_attempt` and the adapter classes if they are no
   longer used anywhere else.
3. Keep `tools/rag/enrichment_backends.py` in place – it is safe to leave even
   if `qwen_enrich_batch` stops using it.
