#!/usr/bin/env bash
set -euo pipefail

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXEC_ROOT="${LLMC_EXEC_ROOT:-$SCRIPT_ROOT}"
REPO_ROOT="${LLMC_TARGET_REPO:-$EXEC_ROOT}"

print_usage() {
  echo "Usage: $0 [--repo PATH] <path> [path ...]" >&2
}

ARGS=()
while (($#)); do
  case "$1" in
    --repo)
      if [ $# -lt 2 ]; then
        print_usage
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
      print_usage
      exit 0
      ;;
    --)
      shift
      ARGS+=("$@")
      break
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done

set -- "${ARGS[@]}"

if [ "$#" -eq 0 ]; then
  print_usage
  exit 1
fi

export LLMC_TARGET_REPO="$REPO_ROOT"

PYTHON_BIN=${PYTHON_BIN:-}
if [ -n "${RAG_VENV:-}" ] && [ -x "$RAG_VENV/bin/python" ]; then
  PYTHON_BIN="$RAG_VENV/bin/python"
elif [ -x "$REPO_ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
elif [ -x "$EXEC_ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$EXEC_ROOT/.venv/bin/python"
elif [ -x "$REPO_ROOT/.direnv/python" ]; then
  PYTHON_BIN="$REPO_ROOT/.direnv/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python}"
fi

# Convert input paths to repo-relative entries and feed through stdin for rag sync.
TMP_INPUT=$(mktemp)
trap 'rm -f "$TMP_INPUT"' EXIT
for path in "$@"; do
  abs="$(realpath "$path")"
  if [[ "$abs" != "$REPO_ROOT"* ]]; then
    echo "Skipping $path (outside repo root $REPO_ROOT)" >&2
    continue
  fi
  rel="$(realpath --relative-to="$REPO_ROOT" "$abs")"
  printf '%s\n' "$rel" >>"$TMP_INPUT"
done

(
  cd "$REPO_ROOT"
  PYTHONPATH="$EXEC_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON_BIN" -m llmc.rag.cli sync --stdin < "$TMP_INPUT"
)
