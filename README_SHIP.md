# LLMC Production Kit — Drop‑In Packaging & Quickstart

Turn your existing repo into a shippable RAG toolkit with a CLI and a tiny HTTP API.

## 1) Drop the kit into your repo root
```
unzip llmc_production_kit.zip -d .
```

## 2) Local install
```
python3 -m venv .venv
./.venv/bin/pip install -U pip wheel
# base + api + embed extras for full functionality
./.venv/bin/pip install -e .[api,embed]
./.venv/bin/rag --help
```

## 3) Quickstart
```
./.venv/bin/rag index
./.venv/bin/rag embed --execute          # if your engine requires embeddings before search
./.venv/bin/rag search "refresh the RAG index" --json
```

## 4) API
```
./.venv/bin/uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
# -> http://127.0.0.1:8000/docs
```

## 5) Docker
```
docker build -t llmc-rag .
docker run --rm -it -p 8000:8000 -v "$PWD:/app" llmc-rag
```

## 6) Compose
> Note: this compose file assumes it lives at the **repo root** so it can see `tools/rag/`.

```
docker compose up --build
```

## Config
See `llmc.toml`. The kit loads TOML and maps to env vars; **env overrides win**.
Common knobs:
- `embeddings.preset` → `EMBEDDINGS_MODEL_PRESET`
- `embeddings.model`  → `EMBEDDINGS_MODEL_NAME`
- `storage.index_path` → `LLMC_RAG_INDEX_PATH`

## Optional: pure CLI with TOML
Use `scripts/ragx` to apply `llmc.toml` before invoking the engine:
```
scripts/ragx index && scripts/ragx embed --execute && scripts/ragx search "foo" --json
```

## Ship checklist
- [ ] `pip install -e .[api,embed]` works
- [ ] `rag index && rag embed --execute` completes
- [ ] `rag search "foo" --json` returns results
- [ ] API runs (`/docs` visible)
- [ ] Docker image responds on `:8000`

