# rag_refresh_watch.sh — tmux Controller for Periodic Refresh

Path
- scripts/rag_refresh_watch.sh (executable)

Purpose
- Manage a long‑running tmux session (`rag-refresh`) that repeatedly executes `scripts/rag_refresh.sh` with a large timeout. Provides simple start/stop/status/restart/toggle actions.

Usage
- `scripts/rag_refresh_watch.sh [start|stop|status|restart|toggle]` (default: `toggle`)

Env
- `RAG_REFRESH_TIMEOUT` (default `12h`), `TMUX_BIN` (default `tmux`)

Notes
- Uses `scripts/run_in_tmux.sh` for consistent logs under `/tmp/codex-work/rag-refresh/`.
