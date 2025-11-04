#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INTERVAL="${RAG_REFRESH_INTERVAL:-3600}"

echo "[rag-refresh-loop] Starting loop with interval ${INTERVAL}s"

while true; do
  start_ts=$(date -Is)
  echo "[rag-refresh-loop] Tick @ $start_ts"
  if ! "$ROOT/scripts/rag_refresh.sh"; then
    echo "[rag-refresh-loop] refresh failed (exit $?)" >&2
  fi
  sleep "$INTERVAL"
done
