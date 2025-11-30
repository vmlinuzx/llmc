# Implementation SDD – RAG Doctor

## 1. Phases

### Phase 1 – Core Doctor Module

**Files:**
- `tools/rag/doctor.py` (new)

**Work:**
- Implement `run_rag_doctor(repo_path, verbose=False)`.
- Implement `format_rag_doctor_summary(result, repo_name)`.
- Use `index_path_for_read()` to locate the DB.
- Use existing `Database` class and connection.

**Complexity Matrix:**
- CP: Med (needs DB schema understanding, but contained to RAG).
- TI: High (pure read-only queries, deterministic).
- DP: Safe (additive, new file only).

---

### Phase 2 – CLI Wiring (`rag doctor`)

**Files:**
- `tools/rag/cli.py`

**Work:**
- Replace existing `doctor()` implementation to call `tools.rag.doctor`.
- Add `--json` and `--verbose` options.
- Wire exit codes based on `result["status"]`.

**Complexity Matrix:**
- CP: Low/Med (needs only CLI + doctor API).
- TI: High (can be tested with a temporary DB / mocked DB).
- DP: Caution (modifies existing command implementation but not behavior of other commands).

---

### Phase 3 – Service Log Integration

**Files:**
- `tools/rag/service.py`

**Work:**
- After enrichment, insert a call to `run_rag_doctor()` and log the summary.
- Wrap in `try/except` so doctor failures never kill the service loop.

**Complexity Matrix:**
- CP: Med (touches the service loop but not core scheduling state).
- TI: Med (needs integration test / smoke test against a real DB).
- DP: Caution (modifies logging path, but should not affect core behavior).

## 2. Risk Notes

- Doctor is read-only: no writes, no schema changes → low blast radius.
- SQL uses existing tables and primary keys only.
- Service integration is wrapped in `try/except` and logs failures, so the worst case is "no doctor output this cycle".

## 3. Test Strategy

- Unit-style:
  - Create a small temp repo + DB with:
    - 1–2 files, a handful of spans.
    - Mix of enriched / not enriched.
    - Mix of embedded / not embedded.
  - Assert `run_rag_doctor()` returns the expected counts and `status`.

- CLI:
  - Run `rag doctor --json` in a repo with a known state and validate JSON keys.
  - Run `rag doctor` and assert exit codes for:
    - Empty DB.
    - Normal backlog.
    - No DB.

- Service (smoke):
  - Run `llmc-rag-service` against a test repo for a couple of cycles.
  - Confirm logs include the `🧪 RAG doctor` line between enrichment and embedding messages.
