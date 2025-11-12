# start_rag_refresh_loop.sh — Simple Loop Refresher

Path
- scripts/start_rag_refresh_loop.sh

Purpose
- Minimal forever loop that calls `scripts/rag_refresh.sh` every `RAG_REFRESH_INTERVAL` seconds.

Usage
- `scripts/start_rag_refresh_loop.sh` (typically launched via `scripts/run_in_tmux.sh`)

Env
- `RAG_REFRESH_INTERVAL` (seconds, default 3600)

