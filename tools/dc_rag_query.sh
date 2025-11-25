#!/usr/bin/env bash
#
# dc_rag_query.sh - Desktop Commander RAG Query Wrapper
#
# Dead simple wrapper for Desktop Commander to query LLMC RAG indices.
# Auto-detects repo root, activates venv, runs the query, returns JSON.
#
# Usage:
#   ./dc_rag_query.sh "authentication logic" [--limit 5] [--repo /path/to/repo]
#
# Environment:
#   LLMC_REPO_ROOT - Override repo detection
#
# Returns:
#   JSON array of results or error message to stderr

set -euo pipefail

err() {
  printf 'dc_rag_query: ERROR: %s\n' "$*" >&2
  exit 1
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

# Defaults
QUERY=""
LIMIT=5
REPO_ROOT=""

# Parse args
while [ "$#" -gt 0 ]; do
  case "$1" in
    --limit)
      shift
      LIMIT="${1:-5}"
      ;;
    --repo)
      shift
      REPO_ROOT="${1:-}"
      ;;
    --help|-h)
      cat <<EOF
Usage: $0 "search query" [--limit N] [--repo /path/to/repo]

Query LLMC RAG index for relevant code spans.

Options:
  --limit N         Max results (default: 5)
  --repo /path      Override repo root detection
  --help            Show this help

Environment:
  LLMC_REPO_ROOT    Override repo detection

Examples:
  $0 "JWT validation"
  $0 "schema enrichment" --limit 10
  $0 "authentication" --repo ~/src/llmc
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
  err "No query provided. Usage: $0 \"search query\" [--limit N]"
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
  err "No .venv found at $VENV - run: python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
fi

# Check for RAG CLI
if [ ! -f "$REPO_ROOT/tools/rag/cli.py" ]; then
  err "RAG CLI not found at $REPO_ROOT/tools/rag/cli.py"
fi

# Run the query
cd "$REPO_ROOT"
source "$VENV/bin/activate"
exec python3 -m tools.rag.cli search "$QUERY" --limit "$LIMIT" --json
