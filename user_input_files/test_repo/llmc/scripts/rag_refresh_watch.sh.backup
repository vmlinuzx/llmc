#!/usr/bin/env bash
# rag_refresh_watch — tmux controller for the RAG enrichment loop (session “rag-refresh”)
set -euo pipefail

SESSION="rag-refresh"
CMD="./scripts/rag_refresh.sh"
TMUX_BIN="${TMUX_BIN:-tmux}"
RUNNER="./scripts/run_in_tmux.sh"

die() {
  echo "[rag_refresh_watch] $*" >&2
  exit 1
}

ensure_tmux() {
  if ! command -v "$TMUX_BIN" >/dev/null 2>&1; then
    die "tmux not found on PATH"
  fi
}

session_exists() {
  "$TMUX_BIN" has-session -t "$SESSION" 2>/dev/null
}

start_session() {
  ensure_tmux
  if session_exists; then
    echo "[rag_refresh_watch] session '$SESSION' already running"
    exit 0
  fi
  if [ ! -x "$RUNNER" ]; then
    die "missing helper $RUNNER (expected executable)"
  fi
  echo "[rag_refresh_watch] starting $CMD under session '$SESSION'"
  "$RUNNER" -s "$SESSION" -T "${RAG_REFRESH_TIMEOUT:-12h}" -- "$CMD"
}

stop_session() {
  ensure_tmux
  if ! session_exists; then
    echo "[rag_refresh_watch] session '$SESSION' is not running"
    exit 0
  fi
  echo "[rag_refresh_watch] stopping session '$SESSION'"
  "$TMUX_BIN" kill-session -t "$SESSION"
}

show_status() {
  if session_exists; then
    echo "[rag_refresh_watch] session '$SESSION' is running"
    exit 0
  fi
  echo "[rag_refresh_watch] session '$SESSION' is stopped"
}

toggle_session() {
  if session_exists; then
    stop_session
  else
    start_session
  fi
}

usage() {
  cat <<'EOF'
Usage: llmc/scripts/rag_refresh_watch.sh [start|stop|status|restart|toggle]
  start    Launch rag_refresh.sh in tmux session "rag-refresh"
  stop     Kill the session if it is running
  status   Report whether the session is active
  restart  Stop then start
  toggle   Flip between running/stopped (default)
EOF
}

action="${1:-toggle}"

case "$action" in
  start)   start_session ;;
  stop)    stop_session ;;
  status)  show_status ;;
  restart) stop_session || true; start_session ;;
  toggle)  toggle_session ;;
  -h|--help|help) usage ;;
  *) usage; die "unknown action: $action" ;;
esac
