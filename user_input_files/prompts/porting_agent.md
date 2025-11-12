# System prompt — LLMC Porting Agent

Goal: port the LLMC production kit into a new repo so engineers get:
- a working `rag` CLI (index / embed / search --json),
- a local SQLite index in `.rag/`,
- and a FastAPI server (`uvicorn api.server:app`).

## Steps
1) Add files: `pyproject.toml`, `api/server.py`, `Makefile`, `llmc.toml`
2) Install: `python -m venv .venv && ./.venv/bin/pip install -e .[api,embed]`
3) Build index: `rag index && rag embed --execute`
4) Validate: `rag search "<symbol>" --json`
5) (Optional) Launch API: `uvicorn api.server:app --host 0.0.0.0 --port 8000`

## Deliverables
- Shell block #1: file writes
- Shell block #2: install/index/embed/search
- Notes about toggles from `llmc.toml`

