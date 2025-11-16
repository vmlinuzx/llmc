# Implementation SDD — LLMC RAG Nav Task 1: Index Status Metadata

## 1. Modules and Functions

### 1.1 `tools.rag_nav.models`

- Defines `IndexState` literal type.
- Defines `IndexStatus` dataclass with the fields described in the SDD.
- Adds placeholder dataclasses:
  - `SnippetLocation`
  - `Snippet`
  These will be used by later tasks (where-used / lineage) but are safe
  to define now and keep this module stable.

### 1.2 `tools.rag_nav.metadata`

- `STATUS_FILENAME = "rag_index_status.json"`

- `_status_dir(repo_root: Path) -> Path`
  - Private helper returning `${repo_root}/.llmc`.
  - Centralizes layout in case we need to adjust later.

- `status_path(repo_root: Path) -> Path`
  - Public helper returning full path to the status file.

- `load_status(repo_root: Path) -> Optional[IndexStatus]`
  - Reads the JSON file from `status_path`.
  - Handles errors:
    - `FileNotFoundError` → returns `None`.
    - Other `OSError` → returns `None`.
    - `JSONDecodeError` → returns `None`.
    - Missing/invalid fields → returns `None`.
  - Validates `index_state` against the allowed literals.
  - Constructs an `IndexStatus` instance from the JSON fields.

- `save_status(repo_root: Path, status: IndexStatus) -> Path`
  - Ensures `${repo_root}/.llmc` exists.
  - Builds a simple dict payload from `IndexStatus`.
  - Writes to a temporary file in the same directory via `tempfile.mkstemp`.
  - Flushes and `fsync`s to minimize risk of partial writes.
  - Uses `os.replace(tmp, final)` for an atomic swap.
  - Cleans up the temporary file on failure (best effort).

## 2. Error Handling and Edge Cases

- Missing status file is **not an error**; callers interpret `None` as
  “no status/unknown freshness”.
- Corrupt JSON or unexpected structure are treated the same way to keep
  higher-level logic simple.
- If the status directory cannot be created or written, `save_status`
  will raise an `OSError` — this should be surfaced to the caller as
  a fatal condition (e.g., log + fail the indexing run).

## 3. Compatibility and Future Work

- `IndexStatus` includes `schema_version` so future changes to the graph
  format can be gated by a simple equality check in the Context Gateway.
- Placeholder `SnippetLocation` and `Snippet` types are defined now to
  avoid future circular-import issues once tool handlers and result
  types are added.
- No public functions depend on MCP or the RAG daemon, so this module
  can be reused from CLI tools, daemons, or tests without extra
  dependencies.

## 4. Testing Details

`tests/test_rag_nav_metadata.py` contains three tests:

- `test_load_status_missing_returns_none`
  - Verifies `load_status` returns `None` when the status file is absent.

- `test_load_status_corrupt_returns_none`
  - Writes a syntactically invalid JSON string and verifies
    `load_status` returns `None`.

- `test_save_and_load_round_trip`
  - Constructs a sample `IndexStatus`.
  - Calls `save_status` and verifies:
    - The returned path matches `status_path`.
    - The file exists on disk.
  - Calls `load_status` and asserts the loaded status equals the original.

