#!/usr/bin/env bash
#
# dc_rag_plan.sh - Desktop Commander RAG Planner Wrapper
#
# Schema-aware retrieval planner for LLMC RAG with symbol matching,
# confidence scoring, and graph-enriched results.
#
# Usage:
#   ./dc_rag_plan.sh "How does JWT validation work?"
#   ./dc_rag_plan.sh "schema enrichment" --limit 10 --min-score 0.5
#
# Environment:
#   LLMC_REPO_ROOT - Override repo detection

set -euo pipefail

err() {
  printf 'dc_rag_plan: ERROR: %s\n' "$*" >&2
  exit 1
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

# Defaults
QUERY=""
LIMIT=5
MIN_SCORE=0.4
MIN_CONFIDENCE=0.6
NO_LOG=""
REPO_ROOT=""

# Parse args
while [ "$#" -gt 0 ]; do
  case "$1" in
    --limit)
      shift
      LIMIT="${1:-5}"
      ;;
    --min-score)
      shift
      MIN_SCORE="${1:-0.4}"
      ;;
    --min-confidence)
      shift
      MIN_CONFIDENCE="${1:-0.6}"
      ;;
    --no-log)
      NO_LOG="--no-log"
      ;;
    --repo)
      shift
      REPO_ROOT="${1:-}"
      ;;
    --help|-h)
      cat <<EOF
Usage: $0 "natural language query" [OPTIONS]

Generate structured retrieval plan with symbol matching and confidence scores.

Options:
  --limit N              Max spans (default: 5)
  --min-score F          Min span score (default: 0.4)
  --min-confidence F     Confidence threshold (default: 0.6)
  --no-log               Skip logging metrics
  --repo /path           Override repo root
  --help                 Show this help

Examples:
  $0 "How does authentication work?"
  $0 "schema enrichment logic" --limit 10
  $0 "JWT validation flow" --min-score 0.5 --min-confidence 0.7
EOF
      exit 0
      ;;
    *)
      if [ -z "$QUERY" ]; then
        QUERY="$1"
      else
        QUERY="$QUERY $1"
      fi
      ;;
  esac
  shift || break
done

# Validate query
if [ -z "$QUERY" ]; then
  err "No query provided. Usage: $0 \"natural language query\""
fi

# Detect repo root
if [ -z "$REPO_ROOT" ]; then
  REPO_ROOT="${LLMC_REPO_ROOT:-}"
fi

if [ -z "$REPO_ROOT" ]; then
  if have_cmd git && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    REPO_ROOT="$(git rev-parse --show-toplevel)"
  else
    REPO_ROOT="$(pwd)"
  fi
fi

REPO_ROOT="$(realpath "$REPO_ROOT")"

if [ ! -d "$REPO_ROOT" ]; then
  err "Repo root not found: $REPO_ROOT"
fi

# Check for venv
VENV="$REPO_ROOT/.venv"
if [ ! -d "$VENV" ]; then
  err "No .venv found at $VENV"
fi

# Check for RAG CLI
if [ ! -f "$REPO_ROOT/tools/rag/cli.py" ]; then
  err "RAG CLI not found at $REPO_ROOT/tools/rag/cli.py"
fi

# Run the planner
cd "$REPO_ROOT"
source "$VENV/bin/activate"
exec python3 -m tools.rag.cli plan \
  "$QUERY" \
  --limit "$LIMIT" \
  --min-score "$MIN_SCORE" \
  --min-confidence "$MIN_CONFIDENCE" \
  $NO_LOG
