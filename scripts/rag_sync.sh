#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$#" -eq 0 ]; then
  echo "Usage: $0 <path> [path ...]" >&2
  exit 1
fi

PYTHON_BIN=${PYTHON_BIN:-}
if [ -n "${RAG_VENV:-}" ] && [ -x "$RAG_VENV/bin/python" ]; then
  PYTHON_BIN="$RAG_VENV/bin/python"
elif [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
elif [ -x "$ROOT/.direnv/python" ]; then
  PYTHON_BIN="$ROOT/.direnv/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python}"
fi

# Convert input paths to repo-relative entries and feed through stdin for rag sync.
TMP_INPUT=$(mktemp)
trap 'rm -f "$TMP_INPUT"' EXIT
for path in "$@"; do
  abs="$(realpath "$path")"
  if [[ "$abs" != "$ROOT"* ]]; then
    echo "Skipping $path (outside repo root $ROOT)" >&2
    continue
  fi
  rel="$(realpath --relative-to="$ROOT" "$abs")"
  printf '%s\n' "$rel" >>"$TMP_INPUT"
done

cat "$TMP_INPUT" | "$PYTHON_BIN" -m tools.rag.cli sync --stdin
