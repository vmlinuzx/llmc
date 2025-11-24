# Ship Worthy Refactor Plan

## Objective
Make the LLMC repo portable and "ship worthy" by removing hardcoded paths and improving developer experience.

## Tasks

### 1. The Purge: Remove Hardcoded Paths (/home/vmlinux)
- **Target**: ~40 occurrences of `/home/vmlinux/src/llmc`.
- **Strategy**:
  - **Tests**: Replace `sys.path.insert` with `conftest.py` logic or rely on installed package. Use `pathlib` for relative paths.
  - **Scripts**: Use `$(dirname "$0")` or python `__file__` relative paths.
  - **Configs**: Ensure defaults use `~` or relative paths.
  - **Docs**: Replace with placeholders like `~/src/llmc` or generic instructions.

### 2. Test Import Fixes
- **Target**: `tests/*.py`
- **Action**: Remove `sys.path.insert(0, ...)` boilerplate. Ensure `conftest.py` sets up the environment correctly or assume `pip install -e .` has been run.

### 3. Documentation Cleanup
- **Target**: `README.md`, `AGENTS.md`.
- **Action**: Genericize installation instructions and path references.

## Workflow
1. Open file to change.
2. User reviews/edits.
3. Ren applies specific fixes if needed (or user does it in the editor).
4. Verify.
