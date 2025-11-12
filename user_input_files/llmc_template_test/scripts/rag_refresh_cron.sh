#!/usr/bin/env bash
set -euo pipefail

# cron-friendly wrapper for scripts/rag_refresh.sh with locking + logging

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXEC_ROOT="${LLMC_EXEC_ROOT:-$SCRIPT_ROOT}"
REPO_ROOT="${LLMC_TARGET_REPO:-$EXEC_ROOT}"
PASSTHRU=()

usage() {
  echo "Usage: $0 [--repo PATH] [options...]" >&2
}

while (($#)); do
  case "$1" in
    --repo)
      if [ $# -lt 2 ]; then
        usage
        exit 1
      fi
      REPO_ROOT="$(realpath "$2")"
      shift 2
      ;;
    --repo=*)
      REPO_ROOT="$(realpath "${1#*=}")"
      shift 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      PASSTHRU+=("$1")
      shift
      ;;
  esac
done

set -- "${PASSTHRU[@]}"
export LLMC_TARGET_REPO="$REPO_ROOT"

LOCK_FILE="${RAG_REFRESH_LOCK_FILE:-$REPO_ROOT/.llmc/.rag/rag_refresh.lock}"
LOG_DIR="${RAG_REFRESH_LOG_DIR:-$REPO_ROOT/logs}"
LOG_FILE="${RAG_REFRESH_LOG_FILE:-$LOG_DIR/rag_refresh.log}"

mkdir -p "$LOG_DIR" "$(dirname "$LOCK_FILE")"

# Acquire non-blocking lock to avoid overlapping refreshes.
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
  timestamp="$(date -Is)"
  echo "[$timestamp] [rag-refresh-cron] Another refresh is already running (lock: $LOCK_FILE); exiting."
  exit 0
fi

# Send stdout/stderr to both console and log.
exec > >(tee -a "$LOG_FILE")
exec 2>&1

timestamp_start="$(date -Is)"
echo "[$timestamp_start] [rag-refresh-cron] Starting refresh (pid $$)"

if [ -x "$EXEC_ROOT/scripts/deep_research_ingest.sh" ]; then
  echo "[$timestamp_start] [rag-refresh-cron] Ingesting manual deep research notes (if any)."
  "$EXEC_ROOT/scripts/deep_research_ingest.sh" --repo "$REPO_ROOT"
fi

exit_code=0
if ! "$EXEC_ROOT/scripts/rag_refresh.sh" --repo "$REPO_ROOT" "$@"; then
  exit_code=$?
fi

timestamp_end="$(date -Is)"
if [ "$exit_code" -eq 0 ]; then
  echo "[$timestamp_end] [rag-refresh-cron] Completed successfully."
else
  echo "[$timestamp_end] [rag-refresh-cron] Failed with exit code $exit_code."
fi

exit "$exit_code"
