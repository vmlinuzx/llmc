# Agent Prompt – Implement Enrichment Backend Cascade Integration (Phase 4)

You are a senior implementation agent working on the LLMC repository.

Your task is to integrate the enrichment backend cascade into the
`scripts/qwen_enrich_batch.py` driver, using the provided patch files in this
zip and following good Git/GitHub practices.

---

## Objectives

1. Wire `scripts/qwen_enrich_batch.py` to call into
   `tools.rag.enrichment_backends.BackendCascade` instead of invoking
   `call_qwen` + `parse_and_validate` directly.
2. Preserve all existing CLI behaviour, router logic, and host fail‑over.
3. Ensure tests pass and prepare the changes for a clean PR.

---

## Implementation Steps

1. **Create a working branch**

   - Suggested branch name:
     - `feature/enrichment-backend-cascade-phase4`

2. **Apply the patch contents**

   - Copy the files from this zip into the repo root, preserving paths:
     - `scripts/qwen_enrich_batch.py`
     - `tools/rag/enrichment_backends.py`
     - `tests/test_enrichment_backends.py`
     - `DOCS/RAG_ENRICHMENT/SDD_Enrichment_Backend_Cascade_Phase4.md`
     - `DOCS/RAG_ENRICHMENT/SDD_Enrichment_Backend_Cascade_Phase4_Impl.md`
     - `DOCS/RAG_ENRICHMENT/AgentPrompt_Enrichment_Backend_Cascade_Phase4.md`

   - Ensure that `tools/rag` is a package (has `__init__.py`) so that the
     new module import works:

     ```python
     from tools.rag.enrichment_backends import (
         BackendError,
         BackendAdapter,
         BackendCascade,
         AttemptRecord,
     )
     ```

3. **Verify the main code changes**

   - In `scripts/qwen_enrich_batch.py` confirm:
     - `_AdapterConfigShim`, `_OllamaBackendAdapter`, `_GatewayBackendAdapter`
       are present between `call_qwen` and `extract_json`.
     - `_build_cascade_for_attempt(...)` is defined before `main()`.
     - The `while attempt_idx < max_attempts:` loop inside `main()` uses
       `BackendCascade.generate_for_span(...)` as described in the SDD.

4. **Run tests**

   - From the repo root, run at minimum:

     ```bash
     python -m pytest tests/test_enrichment_backends.py
     ```

   - If there is an existing LLMC/LLM regression suite, run it as well.
   - Fix any broken imports or minor mismatches, following the intent in the
     SDD and Implementation SDD documents.

5. **Smoke test the enrichment batch**

   - If you have access to Ollama / gateway backends in this environment,
     run a small enrichment batch, for example:

     ```bash
     python scripts/qwen_enrich_batch.py        --backend ollama        --repo-path /path/to/sample/repo        --max-items 3        --verbose
     ```

   - Optionally test with `--backend gateway` when a Gemini/Gateway backend
     is configured.

6. **Git / GitHub hygiene**

   - Stage only the intended files (no editor temp files, no unrelated changes).
   - Use a descriptive commit message, e.g.:

     - `feat(rag): wire qwen_enrich_batch to BackendCascade (phase 4)`

   - Push the branch and open a PR with:
     - Summary of the change.
     - Link/summary of the SDD and Implementation SDD.
     - Notes on tests executed and their outcomes.

---

## Acceptance Criteria

- `qwen_enrich_batch` runs successfully using the new backend cascade and
  produces the same enrichment outputs as before for existing workloads.
- `tools.rag.enrichment_backends` is the single point of truth for backend
  orchestration logic.
- Tests (unit + regression) pass, or any failures are understood and documented
  as out of scope for this phase.
