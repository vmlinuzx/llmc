# scripts/rag — RAG Helper Suite

This folder contains supporting scripts for local RAG development and testing. Key entries:

- `setup_rag.sh` — one‑command venv + requirements install and initial index build.
- `rag_server.py` — lightweight HTTP server for querying the index (dev only).
- `watch_workspace.py` — filesystem watcher that syncs changes into the index.
- `index_workspace.py` — batch indexer for an entire workspace.
- `ast_chunker.py` — language‑aware tree‑sitter chunker used by indexers.
- `query_context.py` — ad‑hoc retrieval helper for local debugging.
- `requirements.txt` — python dependencies for the RAG tools.
- `README.md`, `TESTING.md`, `QUICK_START.txt`, `START_HERE.txt` — guidance for setup and validation.

Notes
- See DOCS/preprocessor_flow.md for the high‑level pipeline used by wrappers outside this folder.

