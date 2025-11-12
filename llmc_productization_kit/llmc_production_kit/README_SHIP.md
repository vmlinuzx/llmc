# LLMC Production Kit — Drop‑In Packaging & Quickstart

This turns your existing repo into a shippable, reusable RAG toolkit with a CLI and a tiny HTTP API.

**What you get**
- Installable package exposing `rag` CLI (reuses your `tools/rag/cli.py`).
- Minimal FastAPI server: `/index`, `/search`, `/health`.
- Docker/Compose for reproducible runs.
- Makefile and scripts for cheap/lazy workflows.
- `llmc.toml` for simple toggles.
- Optional GitHub Action to build/upload your `.rag` index.

---

## 1) Drop the kit into your repo root

```
unzip llmc_production_kit.zip -d .
```

## 2) Local install

```
python3 -m venv .venv
./.venv/bin/pip install -U pip wheel
./.venv/bin/pip install -e .
./.venv/bin/rag --help
```

## 3) Quickstart

```
./.venv/bin/rag index
./.venv/bin/rag search "refresh the RAG index"
```

## 4) API

```
./.venv/bin/pip install fastapi uvicorn
./.venv/bin/python api/server.py
# -> http://127.0.0.1:8000/docs
```

## 5) Docker

```
docker build -t llmc-rag .
docker run --rm -it -p 8000:8000 -v "$PWD:/app" llmc-rag
```

## 6) Compose

```
docker compose up --build
```

---

## Config

See `llmc.toml`. Env vars override file values. Common knobs:
- `EMBEDDINGS_MODEL_PRESET=e5|e5-large|mini`
- `INDEX_PATH=.rag/index_v2.db`

---

## Ship checklist

- [ ] `pip install -e .` works
- [ ] `rag index` builds `.rag/index_v2.db`
- [ ] `rag search "foo"` returns results
- [ ] API runs (`/docs` visible)
- [ ] (opt) Docker image works
