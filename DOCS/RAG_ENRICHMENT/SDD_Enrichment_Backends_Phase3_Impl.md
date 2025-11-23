# Implementation Notes – Phase 3 Cascade Builder

## Files

- `scripts/qwen_enrich_batch.py`
  - Added `_build_cascade_for_attempt(...)` helper above `main()`.
- `tests/test_enrichment_cascade_builder.py`
  - New tests to validate helper behaviour with faked adapters.

## Behaviour

- No runtime changes in Phase 3:
  - The main enrichment loop still uses the existing `call_qwen` +
    `parse_and_validate` pattern.
  - Backend selection, host rotation, and router policy remain exactly as
    before.
- The new helper simply encapsulates the logic for constructing a
  `BackendCascade` and the associated preset + host metadata.

## Why This Helper Matters

- Avoids duplicating tier/back-end/host selection logic when we migrate
  to a cascade-driven loop.
- Gives us a focused, easily testable unit that controls:
  - Which adapter type is used (Ollama vs gateway).
  - Which preset tier is applied (`7b` vs `14b`).
  - Which Ollama host is targeted for a given attempt index.
- Future phases can safely refactor the inner loop by:
  - Calling `_build_cascade_for_attempt(...)` to get a cascade and metadata.
  - Replacing direct `call_qwen(...)` calls with
    `cascade.generate_for_span(...)`.
  - Reusing existing logging/metrics code with minimal changes.

## How to Use in Future Refactors

A future implementation can sketch the per-attempt logic as:

```python
cascade, preset_key, tier_preset, host_label, host_url, selected_backend = _build_cascade_for_attempt(
    backend=backend,
    tier_for_attempt=tier_for_attempt,
    repo_root=repo_root,
    args=args,
    ollama_host_chain=ollama_host_chain,
    current_host_idx=current_host_idx,
    host_chain_count=host_chain_count,
)

# Then call:
result, meta, cascade_attempts = cascade.generate_for_span(prompt, item=item)
```

This keeps the complex retry/host/tier policy decisions where they are
today, while letting the actual LLM invocation be driven by the cascade.
