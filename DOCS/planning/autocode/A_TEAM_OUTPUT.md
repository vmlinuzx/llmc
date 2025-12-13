# A-Team Output — Domain RAG Tech Docs Phase 1

## Changes Implemented

### AC-1: Deterministic Index Naming
- Created `tools/rag/index_naming.py` with `resolve_index_name` function.
- Created `tests/rag/test_index_naming.py` with 4 test cases covering shared/per-repo modes and suffix handling.

### AC-2: Structured Diagnostic Logs
- Modified `tools/rag/indexer.py` to calculate domain and index name for each file during indexing.
- Added structured logging (INFO level) emitting `domain`, `override`, `index`, `extractor`, `chunks`, and `ms` for every processed file.

### AC-3: CLI Flag `--show-domain-decisions`
- Modified `tools/rag/cli.py` to add `--show-domain-decisions` flag to the `index` command.
- Updated `tools/rag/indexer.py` to accept this flag and output user-facing decision logs (`INFO indexer: ...`) when enabled.
- Implemented `_resolve_domain` helper in `indexer.py` to handle path overrides, extensions, and default domains.

### AC-4: Config Schema Extension
- Verified that `tools/rag/config.py` already contains helpers (`get_repository_domain`, `get_path_overrides`) to parse the `[repository]` section from `llmc.toml`.
- The indexer now actively consumes these values to drive domain resolution.

## Test Results

### Unit Tests
- `pytest tests/rag/test_index_naming.py`: **PASS** (4 passed)
- `pytest tests/rag/test_indexer_domain_logic.py`: **PASS** (1 passed)
  - This new test mocks the filesystem and config to verify that `index_repo` correctly logs both the structured metrics (AC-2) and the CLI output (AC-3) with correct domain resolution logic.

## Disagreements / Notes
- No disagreements with requirements.
- AC-4 was largely pre-stubbed in `config.py`, so work focused on consuming it in `indexer.py`.
- Added `tests/rag/test_indexer_domain_logic.py` as a permanent regression test for the logging logic.

---
SUMMARY: Implemented index naming, structured logging, domain resolution logic, and CLI flag; verified with new unit and integration tests.
