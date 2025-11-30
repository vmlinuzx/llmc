# Agent Prompt – Implement RAG Doctor Patch for LLMC

You are an implementation agent working on the LLMC repo.

## Goal

Implement the "RAG doctor" feature that:

- Adds a read-only diagnostics module `tools/rag/doctor.py`.
- Wires a `rag doctor` CLI command.
- Integrates doctor output into the RAG service logs between enrichment and embeddings.

## Repo & Constraints

- Repo root: current working directory.
- Python package: `tools.rag`.
- Do **not** change DB schemas.
- Do **not** add external dependencies.
- All changes must be idempotent and safe to apply over existing installations.

## Tasks

1. **Create `tools/rag/doctor.py`:**
   - Implement `run_rag_doctor(repo_path: Path, verbose: bool = False) -> dict`.
   - Implement `format_rag_doctor_summary(result: dict, repo_name: str) -> str`.
   - Use `index_path_for_read(repo_root)` and `Database` to query:
     - files, spans, enrichments, embeddings
     - pending_enrichments, pending_embeddings (profile `default`)
     - orphan_enrichments
   - Return a JSON-friendly report as described in the SDD.
   - Add a `__main__` block for manual testing (`python -m tools.rag.doctor .`).

2. **Update `tools/rag/cli.py`:**
   - Replace the existing `doctor()` command with one that:
     - Calls `run_rag_doctor()`.
     - Supports `--json` and `--verbose` options.
     - Prints JSON or a summary line using `format_rag_doctor_summary()`.
     - Exits with code 0 on `status` in {`OK`, `EMPTY`} and 1 otherwise.

3. **Update `tools/rag/service.py`:**
   - In `RAGService.process_repo`, after enrichment and before embeddings:
     - Import `run_rag_doctor` and `format_rag_doctor_summary`.
     - Call the doctor and print the summary line.
     - Wrap in `try/except` so doctor failures do not break the service loop.

4. **Testing:**
   - Run unit/smoke tests if available (`pytest`, `rag stats`, `rag doctor --json`).
   - Capture before/after behavior for `llmc-rag-service` logging.

## GitHub Best Practices

- Work on a feature branch (e.g., `feature/rag-doctor`).
- Commit logically grouped changes with clear messages:
  - `feat(rag): add doctor module`
  - `feat(rag): wire rag doctor CLI`
  - `feat(rag): log doctor summary in service loop`
- Open a PR with:
  - Summary of changes.
  - Notes on testing performed.
  - Any follow-up work or future enhancements (e.g., more detailed diagnostics).

Focus on minimal, safe changes that deliver immediate observability value.
