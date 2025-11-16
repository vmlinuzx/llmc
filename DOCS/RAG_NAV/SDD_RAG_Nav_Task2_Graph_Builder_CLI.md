# SDD — LLMC RAG Nav Task 2: Graph Builder & CLI

## 1. Scope

Task 2 introduces a **graph-building and status management CLI** for
the experimental RAG Nav subsystem. It builds on Task 1 (IndexStatus
metadata) and delivers:

- A simple graph artifact under `.llmc/rag_graph.json`.
- A CLI to build the graph and inspect index status.
- Minimal git integration to record the commit used for the build.

This task still does **not** wire into the existing RAG daemon or MCP;
it is safe and self-contained.

## 2. Responsibilities

- Discover a conservative set of source files for a repo (Python only,
  for now).
- Write a graph artifact that records:
  - repo path
  - schema version
  - generation timestamp
  - list of discovered files
- Persist a fresh `IndexStatus` record with the same timestamp and
  optional git HEAD SHA.
- Provide a CLI (`llmc-rag-nav`) with:
  - `build-graph`
  - `status`

## 3. Graph Artifact

File: `${REPO_ROOT}/.llmc/rag_graph.json`

Minimal JSON structure for Task 2:

```jsonc
{
  "repo": "/abs/path/to/repo",
  "schema_version": "1",
  "generated_at": "2025-01-01T00:00:00+00:00",
  "files": [
    "module_a.py",
    "pkg/module_b.py"
  ]
}
```

Semantics:

- `repo` — absolute path to the repo root.
- `schema_version` — matches `IndexStatus.schema_version`.
- `generated_at` — ISO 8601 UTC timestamp at build time.
- `files` — sorted list of source files relative to repo root.

This payload is intentionally small; later tasks may extend or replace
it with a richer schema-enriched graph.

## 4. CLI Interface

Command: `llmc-rag-nav` (via `python -m tools.rag_nav.cli` or the
`scripts/llmc-rag-nav` wrapper).

Subcommands:

- `build-graph`
  - Args:
    - `--repo, -r` (default: `.`) — path to repo root.
  - Behaviour:
    - Discovers source files.
    - Writes `.llmc/rag_graph.json`.
    - Writes `.llmc/rag_index_status.json` with `index_state="fresh"`.

- `status`
  - Args:
    - `--repo, -r` (default: `.`)
    - `--json` — emit JSON instead of human-readable text.
  - Behaviour:
    - Reads `IndexStatus` via `load_status`.
    - Prints either a human summary or JSON with status fields.

## 5. Source Discovery

For Task 2, discovery is intentionally conservative:

- Walk the repo root with `os.walk`.
- Skip directories:
  - `.git/`
  - `.llmc/`
  - `.venv/`
  - `__pycache__/`
- Include files ending with `.py` only.

This is sufficient to prove the plumbing; later work may honour
`.gitignore` or include other languages.

## 6. Interactions

- Writes status via `tools.rag_nav.metadata.save_status`.
- Reads status via `tools.rag_nav.metadata.load_status`.
- Uses `git -C <repo> rev-parse HEAD` (if available) to populate
  `last_indexed_commit`.

No other modules are coupled to this task.

## 7. Testing Strategy

- `tests/test_rag_nav_build_graph.py`
  - Creates a temp directory with a tiny fake repo.
  - Writes a couple of `.py` files in nested directories.
  - Calls `build_graph_for_repo(tmp_path)`.
  - Asserts:
    - `.llmc/rag_graph.json` exists and lists the created files.
    - `.llmc/rag_index_status.json` exists.
    - Loaded `IndexStatus` has `index_state="fresh"` and
      `schema_version="1"`.

