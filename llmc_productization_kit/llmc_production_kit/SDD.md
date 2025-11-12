# LLMC Production Kit — Software Design Document (SDD)

**Purpose**  
Make an existing code-aware RAG repo instantly *shippable* with:
- an installable package + CLI (`rag`),
- a tiny HTTP API (FastAPI) for `/index` and `/search`,
- containerization (Docker/Compose),
- dead-simple scripts/Make targets,
- config-by-file (`llmc.toml`) + env overrides,
- optional CI job to build / attach the index artifact.

This kit *wraps* your existing `tools/rag` package (or equivalent) without rewriting core logic. If `tools/rag` isn’t present, the kit still installs; CLI/API methods that import `rag` will error gracefully with actionable messages.

---

## 1. Objectives & Non-Goals

**Objectives**
- One-command local install and smoke test.
- Keep infra cheap: local SQLite index under `.rag/` (no DB server required).
- Make the RAG engine invokable via both CLI and HTTP.
- Let engineers port this kit to other projects with a reproducible checklist.

**Non‑Goals**
- Replacing your RAG/index logic.
- Providing GPU/runtime orchestration.
- Managing secrets/providers beyond standard env vars.

---

## 2. System Overview

```
+---------------------------+
| Your Repo (codebase)      |
|                           |       +---------------------+
| tools/rag/ (existing)     |<----->|  llmc-rag (package) |
|  ├─ cli.py  (entry)       |       |  (this kit)         |
|  ├─ indexer.py            |       +---------------------+
|  └─ search.py             |             ^        ^
+---------------------------+             |        |
                 ^                        |        |
                 | install -e .           |        |
                 |                        |        | imports/fallback
          +------+------------------------+--------+-------------------+
          |                 Surfaces: CLI `rag` and HTTP API           |
          |  - CLI: rag index / rag search                             |
          |  - HTTP: /index, /search                                  |
          +------------------------------------------------------------+
```

- **Packaging** via `pyproject.toml` exposes `rag = rag.cli:cli` (your current CLI) as a console script.
- **API** wraps your indexer/search functions; falls back to shelling the CLI if `import rag` fails.
- **Config** lives in `llmc.toml`; env vars override file values.
- **Container** runs the API; bind mounts repo so `.rag/` persists.

---

## 3. Architecture & Components

### 3.1 Python Package (`llmc-rag`)
- Declared in `pyproject.toml` using `setuptools` finding `tools/rag*`.
- Depends on a minimal set of libs (Click, Sentence-Transformers, Tree-sitter). Adjust as needed.

### 3.2 CLI
- Exposed as `rag` (entry `rag.cli:cli`). No changes to your code required.
- Makefile targets call the CLI for fast muscle memory (`make index`, `make search q="..."`).

### 3.3 HTTP API (FastAPI)
- Endpoints:
  - `POST /index` `{since?: str, no_export?: bool}` → kicks off (re)index.
  - `GET  /search?q=...&limit=5` → returns top-N results.
- Runtime path:
  1. Try **direct import**: `from rag.indexer import index_repo`, `from rag.search import search_spans`.
  2. If import fails, **fallback** to executing `rag` CLI via subprocess.

### 3.4 Config (`llmc.toml`)
- Tunables: embedding preset, storage path override, enrichment toggles.
- Environment variables override file settings to support CI/CD and secrets.

### 3.5 Docker & Compose
- CPU-only base (`python:3.11-slim`).
- Builds the package, exposes API on `:8000` and mounts the repo for persistence.

### 3.6 CI (optional)
- GitHub Actions workflow to run `rag index` on push, upload `.rag/index_v2.db` as artifact.

---

## 4. Data & Storage

- Default index path: `.rag/index_v2.db` (SQLite).  
- Optional export: when available in your `indexer`, keep JSON under `.rag/export/`.
- No remote vector DB assumed; upgrade path is to swap your search/indexer implementation.

---

## 5. Configuration Model

```toml
# llmc.toml
[embeddings]
preset = "e5"          # e5 | e5-large | mini

[storage]
# index_path = ".rag/index_v2.db"

[enrichment]
enabled = false
model = "gpt-4o-mini"
batch_size = 50
```

Resolution order: **env vars > llmc.toml > hardcoded defaults**.

---

## 6. Operational Flows

### 6.1 Indexing
- CLI: `rag index [--since <rev/timestamp>]`
- API: `POST /index`
- Expected outcome: `.rag/index_v2.db` exists; logs written to stdout.

### 6.2 Search
- CLI: `rag search "query" --limit 5`
- API: `GET /search?q=...&limit=5`

### 6.3 Local Dev
- `python -m venv .venv && ./.venv/bin/pip install -e .`
- `make index` then `make search q="symbol or question"`

### 6.4 Container
- `docker build -t llmc-rag .`
- `docker run -it --rm -p 8000:8000 -v "$PWD:/app" llmc-rag`

---

## 7. Logging, Errors, & Observability

- CLI/API print structured log lines (INFO by default).  
- API returns JSON errors with helpful messages when `rag` import/CLI is missing.  
- Health: `GET /health` → `{"ok": true}` if process alive.

---

## 8. Security & Secrets

- No secrets stored by default.  
- If your RAG pulls provider keys, inject via env (e.g., `.env` in dev, GH secrets in CI).  
- Do **not** commit `.rag/` indexes with sensitive content unless intended.

---

## 9. Risks & Mitigations

- **No `tools/rag`:** API falls back to running `rag` if installed; otherwise returns clear error.  
- **C/C++ build deps (tree-sitter):** Provide Dockerfile to guarantee build env.  
- **Large repos slow indexing:** Provide `--since` flag path-through to speed up incremental builds.

---

## 10. Acceptance Criteria

- `pip install -e .` produces a working `rag` command.
- `rag index` creates `.rag/index_v2.db` with no unhandled exceptions.
- `rag search "foo"` returns non-empty results on a repo with content.
- `uvicorn api.server:app` serves `/docs`, `/index`, `/search` successfully.
- Docker image builds and runs API; compose works.

---

## 11. Implementation Plan (for Codex)

1) **Drop kit** files at repo root.  
2) `python3 -m venv .venv && ./.venv/bin/pip install -e .`  
3) Smoke test: `rag index && rag search "README"`  
4) API: `./.venv/bin/pip install fastapi uvicorn && ./.venv/bin/python api/server.py`  
5) (Opt) Docker build & run; (Opt) enable GitHub Action.

---

## 12. File Inventory (delivered by this kit)

- `README_SHIP.md` – Quickstart + checklist
- `SDD.md` – This document
- `pyproject.toml` – Packaging
- `llmc.toml` – Config toggles
- `api/server.py` – FastAPI with import/CLI fallback
- `scripts/bootstrap.py` – One-shot local setup
- `scripts/build_kit.py` – Writes kit files into a target repo
- `Dockerfile`, `compose.yaml`, `Makefile`
- `.github/workflows/index.yml` – Optional CI
- `prompts/porting_agent.md` – Porting prompt

---

## 13. Future Upgrades

- Pluggable vector DBs (Qdrant, Chroma) with env-based switches.
- Richer metrics endpoint (`/metrics` for Prometheus).
- Optional background scheduler for periodic indexing.
