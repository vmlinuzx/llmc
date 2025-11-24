# Ship Worthy Refactor Plan

## Objective
Make the LLMC repo portable and "ship worthy" by removing hardcoded paths and improving developer experience.

## Tasks

### 1. The Purge: Remove Hardcoded Paths (/home/vmlinux)
- [x] **Tests**: Replace `sys.path.insert` with dynamic `REPO_ROOT` or `conftest.py` logic.
    - `tests/test_phase2_enrichment_integration.py` (Done)
    - `tests/test_rag_failures.py` (Done)
    - `tests/test_ast_chunker.py` (Done)
    - `tests/test_repo_add_idempotency.py` (Done)
    - `tests/test_multiple_registry_entries.py` (Done)
    - `tests/test_e2e_daemon_operation.py` (Done)
    - `tests/test_index_status.py` (Done)
    - `tests/test_graph_building.py` (Done)
    - `tests/test_enrichment_data_integration_failure.py` (Done)
- [x] **Scripts**: Use `$(dirname "$0")` or python `__file__` relative paths.
    - `scripts/llmc-route` (Done)
    - `scripts/llmc-clean-logs.sh` (Done)
    - `tools/dc_rag_query.sh` (Done)
- [x] **Docs**: Replace with placeholders like `~/src/llmc` or generic instructions.
    - `DOCS/ROADMAP.md` (Done)
    - `DOCS/DESKTOP_COMMANDER_INTEGRATION.md` (Done)
    - `AGENTS.md` (Done)
    - `README.md` (Done)
- [x] **Configs**: Ensure defaults use `~` or relative paths.
    - `mcp/mcpo.config.json` (Done)

### 2. Verification
- [ ] Run `pytest` to ensure no regressions from path changes.
- [ ] Run `llmc-rag-doctor` or similar check to verify script pathing (if environment allows).

### 3. Test Import Fixes (Broader Scope)
- [ ] **Target**: Remaining `tests/*.py` files that might still have `sys.path` hacks (if any).
- [ ] **Action**: Standardize on `conftest.py` fixtures.

## Workflow
1. Open file to change.
2. User reviews/edits.
3. Ren applies specific fixes if needed (or user does it in the editor).
4. Verify.