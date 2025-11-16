# LLMC RAG Nav — Task 2 System Overview (Graph Builder & CLI)

Task 2 adds a **graph builder** and a small CLI on top of the
index-status layer introduced in Task 1.

## Purpose

Before wiring RAG Nav into daemons or MCP tools, we need a simple,
reliable way to:

- Build a graph artifact for a repo.
- Mark the index as fresh.
- Inspect status from the command line.

This task delivers exactly that, without touching existing RAG
services.

## Key Behaviours

- `llmc-rag-nav build-graph --repo <path>`
  - Scans the repo for `.py` files (skipping `.git`, `.llmc`, `.venv`,
    `__pycache__`).
  - Writes `.llmc/rag_graph.json` with a list of those files and
    basic metadata.
  - Writes `.llmc/rag_index_status.json` marking the index as `fresh`.

- `llmc-rag-nav status --repo <path> [--json]`
  - Reads the `IndexStatus` file.
  - Prints either a human-readable summary or JSON.

## File Locations

- Graph artifact:
  - `${REPO_ROOT}/.llmc/rag_graph.json`
- Index status:
  - `${REPO_ROOT}/.llmc/rag_index_status.json`

Both use atomic write patterns to avoid partial contents.

## How This Fits Into the Bigger Picture

Later tasks (3 and 4) will:

- Replace the minimal graph payload with a richer, schema-enriched
  representation.
- Implement where-used, lineage, and search operations over that graph.
- Add a Context Gateway that decides when to route queries to RAG
  vs. local fallbacks.

This Task 2 slice ensures those future features have a solid,
debuggable foundation.

