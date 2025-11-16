<!--
SOURCE_FILE: tools/create_context_zip.py
SOURCE_HASH: sha256:62f81445e2dacde52b33cc06cf861bc7cc51480686011e6df85cde59e12a5e26
GENERATED_AT_UTC: 2025-11-16T00:47:52Z
-->

# tools/create_context_zip.py – High-Level Overview

**tools/create_context_zip.py** is a tool module providing RAG daemon services, repository integration, or specialized RAG functionality. It supports background processing and infrastructure operations.

## Responsibilities & Behavior (for Humans)

- Implements 5 function(s) for specific operations

## Public Surface Area (API Snapshot)

- `_run(cmd, cwd)`
  Function: _run

- `find_repo_root(start)`
  Return the repository root using git, with a manual fallback.

- `list_included_paths(repo_root)`
  Files that are tracked or untracked-but-not-ignored.

- `next_available_zip_path(dest_dir, base_name)`
  Return a zip path <base_name>.zip or with -N suffix if exists.

- `main()`
  Function: main


## Data & Schema


## Control Flow & Lifecycle

Typical execution flow:
1. Module imported or script executed
2. `main()` called

## Dependencies & Integration Points

**Python Imports**:
- `__future__`
- `datetime`
- `pathlib`
- `subprocess`
- `sys`
- `time`
- `typing`
- `zipfile`


## Configuration & Environment

No specific environment variables detected for this file.

## Error Handling, Edge Cases, and Failure Modes

**Exceptions Raised**:
- `FileNotFoundError` - When required files or directories don't exist
- `ValueError` - For invalid configuration or parameters
- `TimeoutError` - When operations exceed configured timeouts

**Common Failure Modes**:
- Index corruption or missing index files
- LLM provider API failures or rate limits
- Insufficient permissions for file system operations

## Performance & Scaling Notes

This file has no significant performance concerns.

## Security / Footguns

- ⚠️ Shell execution with file paths - ensure paths are validated

## Internal Structure (Technical Deep Dive)

**Implementation Details**:

- Contains 5 function definition(s)

**Key Patterns**:
- Modular design for testability and maintainability
- Separation of concerns between RAG operations
- Async/sync patterns where appropriate

## Example Usage (If Applicable)

```python
from pathlib import Path

# Import and use
# (if this is a standalone module)
# result = _run(cmd, cwd)
```

