# rag_sync.sh — Sync Paths Into RAG Index

Path
- scripts/rag_sync.sh

Purpose
- Convert absolute inputs to repo‑relative paths and feed them to `tools.rag.cli sync --stdin`.

Usage
- `scripts/rag_sync.sh [--repo PATH] <path> [path ...]`

Behavior
- Determines Python interpreter (repo `.venv`, `RAG_VENV`, exec `.venv`, `.direnv`, else `python`)
- Writes normalized relative paths to a temp file and runs the sync command from the repo root

Exit codes
- 0 on success; 1 on usage errors

