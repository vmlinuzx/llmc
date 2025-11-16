# SDD — LLMC RAG Nav Task 1: Index Status Metadata

## 1. Scope

This SDD covers the first increment of the **Schema-Enriched RAG Nav**
subsystem: the metadata layer that tracks index status per repository.

It introduces:

- A stable `IndexStatus` dataclass for status metadata.
- A `.llmc/rag_index_status.json` file per repo.
- Helpers to load and save that file safely.

No existing RAG or daemon behavior is changed by this task.

## 2. Responsibilities

- Provide a **small, durable status record** that other components
  (indexers, daemons, MCP tools) can read/write.
- Avoid crashes on corrupt/missing status files.
- Use an atomic write pattern so higher-level tools never see
  half-written JSON.

## 3. Data Model

```python
IndexState = Literal["fresh", "stale", "rebuilding", "error"]

@dataclass
class IndexStatus:
    repo: str
    index_state: IndexState
    last_indexed_at: str  # ISO 8601 UTC
    last_indexed_commit: Optional[str]
    schema_version: str
    last_error: Optional[str] = None
```

Semantics:

- **repo** — human-readable identifier (usually repo root path).
- **index_state**
  - `fresh`      — graph/index artifacts were built and match HEAD.
  - `stale`      — known to be out of date (e.g., new commits, failed run).
  - `rebuilding` — long-running rebuild in progress.
  - `error`      — last indexing attempt failed; see `last_error`.
- **last_indexed_at** — UTC timestamp of last successful build.
- **last_indexed_commit** — git commit SHA (if available) at build time.
- **schema_version** — version of graph/index format.
- **last_error** — simple message for the last failure (if any).

## 4. File Layout

For a repo with root `${REPO_ROOT}`:

```text
${REPO_ROOT}/.llmc/rag_index_status.json
```

The JSON payload is a direct serialization of `IndexStatus`, with
`last_error` omitted when `null`.

## 5. Interfaces

Module: `tools.rag_nav.metadata`

- `status_path(repo_root: Path) -> Path`
- `load_status(repo_root: Path) -> Optional[IndexStatus]`
- `save_status(repo_root: Path, status: IndexStatus) -> Path`

Error handling:

- `load_status` returns `None` for missing, unreadable, or malformed files.
- `save_status` raises only on unrecoverable filesystem errors; partial
  writes are avoided via temp+replace.

## 6. Constraints and Non-goals

- No freshness logic (e.g., comparing commit to HEAD) is implemented yet;
  that belongs to the **Context Gateway** in a later task.
- No MCP integration or daemon wiring is included here.
- The JSON schema is intentionally simple: no nested objects beyond
  what is needed for status.

## 7. Testing Strategy

Covered by `tests/test_rag_nav_metadata.py`:

- Missing file → `load_status` returns `None`.
- Corrupt JSON → `load_status` returns `None` (no exception).
- Round-trip: `save_status` then `load_status` returns identical
  `IndexStatus` instance.

