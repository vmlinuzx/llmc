# Agent Prompt – Phase 3 Cascade Builder Helper

You are an implementation agent working on the LLMC repository.

Your task in Phase 3 is to introduce a small helper that builds a
`BackendCascade` for a single enrichment attempt, without changing the
current runtime behaviour of `scripts/qwen_enrich_batch.py`.

## Objectives

1. In `scripts/qwen_enrich_batch.py`:
   - Add a new helper function `_build_cascade_for_attempt(...)` directly
     above `main()`.
   - The helper must:
     - Mirror the existing logic for choosing the effective backend
       (`ollama` vs `gateway`) based on the router tier and CLI `--backend`.
     - Derive `preset_key` (`"7b"` vs `"14b"`) and `tier_preset` from
       `PRESET_CACHE`.
     - Construct a single `_OllamaBackendAdapter` or `_GatewayBackendAdapter`
       as appropriate and wrap it in a `BackendCascade`.
     - Return `(cascade, preset_key, tier_preset, host_label, host_url, selected_backend)`.

2. Add unit tests in `tests/test_enrichment_cascade_builder.py` that:
   - Monkeypatch `PRESET_CACHE` to a small deterministic dict.
   - Monkeypatch `_OllamaBackendAdapter` and `_GatewayBackendAdapter` with
     simple fake classes that record constructor arguments.
   - Verify helper behaviour for:
     - Ollama backend (`backend="auto", tier_for_attempt="7b"`).
     - Gateway backend (`backend="gateway", tier_for_attempt="nano"`).
     - Unknown backend string (`backend="weird"` → falls back to Ollama).

3. Do **not** modify the main enrichment loop in this phase.

## Implementation Checklist

1. Implement `_build_cascade_for_attempt(...)` in
   `scripts/qwen_enrich_batch.py` as per the SDD.
2. Create `tests/test_enrichment_cascade_builder.py` with the three tests
   described above.
3. Run:

   ```bash
   pytest tests/test_enrichment_backends.py           tests/test_enrichment_adapters.py           tests/test_enrichment_cascade_builder.py
   ```

4. Commit with a message like:

   > feat(enrich): add backend cascade builder helper

## Git / Patch Guidelines

- Only change the following files in this phase:
  - `scripts/qwen_enrich_batch.py`
  - `tests/test_enrichment_cascade_builder.py`
  - Optional: add/update docs in `DOCS/RAG_ENRICHMENT` for Phase 3.
