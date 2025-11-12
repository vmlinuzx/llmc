# LLMC Productization Kit — Drop‑In Packaging & Quickstart

This kit turns your existing repo (the one you zipped for me) into a shippable, reusable RAG + enrichment toolkit with a one‑command CLI and an optional API.

**What you get**

- `pyproject.toml` to package the existing `tools/rag` as an installable library (`llmc-rag`) with a `rag` CLI.
- A minimal `Dockerfile` (CPU‑only) for reproducible runs.
- `compose.yaml` for a no‑frills local service.
- `Makefile` with lazy targets (`make install`, `make index`, `make search`).
- `scripts/bootstrap.py` to set up a venv in seconds.
- `prompts/porting_agent.md` — a ready system prompt to let an LLM port the template to any new project.
- Optional `api/server.py` — a tiny FastAPI wrapper exposing `/index` and `/search`.

> Works **without** vector DB servers. It uses your repo‑local **SQLite** index at `.rag/index_v2.db` and **E5‑base** embeddings by default.

---

## 1) Drop these files into the ROOT of your repo

Unzip the kit to the root (same folder that contains `tools/rag/cli.py`).

```
unzip llmc_productization_kit.zip -d .
```

## 2) (Fast) Local install

```
python3 -m venv .venv
./.venv/bin/pip install -U pip wheel
./.venv/bin/pip install -e .
```

That gives you a `rag` command:

```
./.venv/bin/rag --help
```

## 3) Quickstart: index and search your repo

```
# from repo root
./.venv/bin/rag index
./.venv/bin/rag search "how do I refresh the RAG index?"
```

> By default we use the **E5‑base** embedding model and store vectors in `.rag/index_v2.db` (SQLite).

## 4) Optional: run as a tiny API

```
./.venv/bin/pip install fastapi uvicorn
./.venv/bin/python api/server.py
# -> http://127.0.0.1:8000/docs
```

### API routes

- `POST /index`  → full or incremental index
- `GET /search?q=...&limit=5`  → cosine search across enriched spans

## 5) Docker (CPU‑only) — reproducible runs

```
docker build -t llmc-rag .
docker run --rm -it -v "$PWD:/app" llmc-rag rag index
docker run --rm -it -p 8000:8000 -v "$PWD:/app" llmc-rag python api/server.py
```

## 6) Compose

```
docker compose up --build
# -> service on http://127.0.0.1:8000
```

---

## What this packages (no code rewrites required)

- Exposes your existing `tools/rag` as installable package **`llmc-rag`**.
- Publishes the CLI entry point: `rag = rag.cli:cli`.
- Keeps your current `.rag` folder, AST chunking, enrichment tables, and planner scoring intact.
- Keeps the model preset switchable via env: `EMBEDDINGS_MODEL_PRESET=e5|e5-large|mini` etc.

### Feature toggles via `llmc.toml`

The included `llmc.toml` shows common knobs (model preset, index path, enrichment switches). Env vars still work and win if both are present.

---

## Port this template to *other* projects (LLM‑assisted)

Use `prompts/porting_agent.md` with your favorite LLM: paste it as the system prompt, paste the new repo’s context zip (or a file list), and paste `llmc.toml`. The agent will output the exact shell steps to add the kit and run `rag index/search`, plus recommended enrichment passes for that codebase.

---

## Ship checklist (cheap + lazy friendly)

- [ ] `pip install -e .` works
- [ ] `rag index` builds `.rag/index_v2.db`
- [ ] `rag search "foo"` returns results
- [ ] (opt) API runs (`/docs` shows up)
- [ ] Commit `pyproject.toml`, `api/`, `Makefile`, `llmc.toml`

**Done. You’ve got a reusable RAG engine with a CLI and API.**
