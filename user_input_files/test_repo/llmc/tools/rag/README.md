# RAG Indexer (prototype)

This directory contains the Python CLI that builds and maintains the `.llmc/.rag/` index described in `DOCS/SETUP/TreeSitter_Backbone.md`.

Quick start:

```bash
python3 -m venv /tmp/rag-venv
source /tmp/rag-venv/bin/activate
pip install -r llmc/tools/rag/requirements.txt
python -m tools.rag.cli --help
```

Key commands:

- `python -m tools.rag.cli index` – full walk of the repo, writes `.llmc/.rag/index_v2.db` (or the path pointed to by `LLMC_RAG_INDEX_PATH`) plus a versioned spans export.
- `python -m tools.rag.cli sync --since <commit>` – incremental update based on git diff.
- `python -m tools.rag.cli sync --stdin` – feed newline-delimited paths via stdin (perfect for editor hooks).
- `python -m tools.rag.cli stats` – quick counts plus estimated remote tokens avoided (`--json` available).
- `python -m tools.rag.cli enrich --dry-run` – preview enrichment work items keyed by `span_hash`. Use `--execute` for the built-in deterministic stub (records summary metadata without calling a remote LLM).
- `python -m tools.rag.cli embed --dry-run` – preview embedding jobs (also keyed by `span_hash`). Use `--execute` to persist normalized `intfloat/e5-base-v2` vectors with the canonical `"passage: "` prefix (override via `--model` or env vars).
- `python -m tools.rag.cli search "jwt validation flow"` – cosine search over the local `.rag` embeddings (outputs JSON with `--json`).
- `python -m tools.rag.cli benchmark` – run the lightweight embedding benchmark harness to ensure the active encoder clears the default quality thresholds (top-1 ≥ 0.75, avg margin ≥ 0.1).

Helper: `llmc/scripts/rag_sync.sh <paths...>` feeds files to `rag sync --stdin` and is used by the editor integrations.

The CLI currently extracts spans for Python, JS/TS/TSX, Go, and Java files. Other grammars are registered but will emit empty spans until we implement per-language walkers.
