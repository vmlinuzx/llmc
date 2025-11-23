# Agent Prompt – Phase 1 Backend Abstraction

Task: add a reusable backend abstraction and cascade helper for enrichment.

1. Add `tools/rag/enrichment_backends.py` defining:
   - `AttemptRecord`
   - `BackendError`
   - `BackendAdapter`
   - `BackendCascade`

2. Add tests in `tests/test_enrichment_backends.py` using fake backends to
   verify:
   - Single-backend success.
   - All-backend failure with correct `failure_type` and `attempts`.

3. Do not modify existing scripts in this phase.
