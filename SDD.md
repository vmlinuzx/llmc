# LLMC Production Kit — Software Design Document (SDD)

## Scope (what this kit does)
Wrap an existing code-aware RAG repo so it ships with:
- an installable package + CLI (`rag`),
- a tiny HTTP API (FastAPI) exposing `/index`, `/search`, `/health`,
- containerization (Docker/Compose),
- lazy Make targets and a bootstrap script,
- config-by-file `llmc.toml` with env overrides (kit loads TOML → sets env),
- optional CI to build and attach the `.rag` index.

This kit does not rewrite your RAG logic. It assumes you already have `tools/rag` (`cli.py`, `indexer.py`, `search.py`). If imports fail, the API falls back to invoking the `rag` CLI.

---

## Architecture

```
Your Repo
  └─ tools/rag/               # existing engine
      ├─ cli.py               # exposes `rag` commands
      ├─ indexer.py
      └─ search.py

Surfaces
  - CLI: rag index / rag embed --execute / rag search --json
  - HTTP: POST /index, GET /search, GET /health
```

Fallbacks: If `import rag` fails, the API shells out to the CLI using equivalent flags and requests JSON where applicable (`--json`).

---

## Packaging

Minimal hard deps in base package; heavier bits behind extras:

```toml
[project.dependencies]
click = ">=8.1.7"
jsonschema = ">=4.23.0"
tree_sitter = "==0.20.1"
tree_sitter_languages = "==1.9.1"
pydantic = ">=2.7.0"
requests = ">=2.31.0"

[project.optional-dependencies]
api = ["fastapi>=0.111", "uvicorn[standard]>=0.30"]
embed = ["sentence-transformers>=3.0.0", "torch>=2.1.0; platform_machine != 'armv7l'"]
```

---

## Configuration

`llmc.toml` is read by the API (and optional CLI wrapper) and mapped to engine env vars.

Examples:
- `embeddings.preset` → `EMBEDDINGS_MODEL_PRESET`
- `embeddings.model`  → `EMBEDDINGS_MODEL_NAME`
- `storage.index_path` → `LLMC_RAG_INDEX_PATH`

Precedence: env vars > llmc.toml > library defaults.

---

## Operational Flows

- Index: `rag index` or `POST /index`
- Embed: `rag embed --execute` (required by typical search engines)
- Search: `rag search "query" --json` or `GET /search?q=...`
- API serve: `uvicorn api.server:app --host 0.0.0.0 --port 8000`

---

## Acceptance Criteria

- `pip install -e .` exposes a working `rag` CLI.
- `rag index && rag embed --execute` completes without unhandled errors.
- `rag search "foo" --json` returns structured results.
- API runs via `uvicorn api.server:app` and returns JSON.
- Docker image serves API on `:8000`.
- CI workflow performs a full index (or an incremental with a proper base SHA).

---

## Notes

- The kit does not modify `tools/rag/config.py`; for pure CLI flows that need TOML, use `scripts/ragx` which loads TOML and execs `rag`.

