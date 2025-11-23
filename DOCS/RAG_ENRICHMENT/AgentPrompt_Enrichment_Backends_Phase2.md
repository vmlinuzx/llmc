# Agent Prompt – Phase 2 Concrete Adapters

You are an implementation agent working on the LLMC repository.

Your task in Phase 2 is to introduce **concrete enrichment backend adapters**
for Ollama and gateway/Gemini, building on the generic abstractions from
`tools.rag.enrichment_backends` (Phase 1). Behaviour of the existing enrichment
loop must remain unchanged in this phase.

## Objectives

1. Update `scripts/qwen_enrich_batch.py` to:
   - Import `BackendError`, `BackendAdapter`, `BackendCascade`, and
     `AttemptRecord` from `tools.rag.enrichment_backends`.
   - Define `_AdapterConfigShim`, `_OllamaBackendAdapter`, and
     `_GatewayBackendAdapter` immediately after `call_qwen` and before
     `extract_json`.

2. Add tests in `tests/test_enrichment_adapters.py` that:
   - Use `monkeypatch` to stub out `call_qwen` and `parse_and_validate`.
   - Verify success + failure behaviour for both adapters.

3. Do **not** modify the main enrichment loop in this phase.

## Implementation Checklist

1. In `scripts/qwen_enrich_batch.py`:
   - Insert:

     ```python
     from tools.rag.enrichment_backends import BackendError, BackendAdapter, BackendCascade, AttemptRecord
     ```

     before `GATEWAY_DEFAULT_TIMEOUT`.

   - Add the adapter definitions between `call_qwen` and `extract_json` as
     described in the SDD.

2. Create `tests/test_enrichment_adapters.py`:
   - Implement tests for:
     - `_OllamaBackendAdapter` success and validation failure.
     - `_GatewayBackendAdapter` success with `GEMINI_MODEL` override and
       validation failure.

3. Run:

   ```bash
   pytest tests/test_enrichment_backends.py tests/test_enrichment_adapters.py
   ```

4. Commit with a message like:

   > feat(enrich): add concrete ollama/gateway adapters

## Git / Patch Guidelines

- The only files that should change in this phase are:
  - `scripts/qwen_enrich_batch.py`
  - `tests/test_enrichment_adapters.py`
  - (optional) any new docs under `DOCS/RAG_ENRICHMENT` related to Phase 2.
