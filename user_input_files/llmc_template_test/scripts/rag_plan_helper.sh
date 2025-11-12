#!/usr/bin/env bash
# Shared helper to render the RAG planner snippet for Codex tooling.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXEC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: rag_plan_helper.sh [--repo PATH]

Reads the user query from stdin and prints the RAG planner snippet if available.
Respects CODEX_WRAP_DISABLE_RAG / LLM_GATEWAY_DISABLE_RAG / LLMC_RAG_INDEX_PATH.
EOF
}

REPO_ROOT="${LLMC_TARGET_REPO:-$EXEC_ROOT}"
PYTHON_BIN="${PYTHON_BIN:-${LLM_GATEWAY_PYTHON:-${PYTHON:-python3}}}"
SCRIPT_PATH="$EXEC_ROOT/scripts/rag_plan_snippet.py"

while (($#)); do
  case "$1" in
    --repo)
      if [ $# -lt 2 ]; then
        echo "rag_plan_helper.sh: --repo requires a path" >&2
        exit 2
      fi
      REPO_ROOT="$(realpath "$2")"
      shift 2
      ;;
    --repo=*)
      REPO_ROOT="$(realpath "${1#*=}")"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "rag_plan_helper.sh: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      echo "rag_plan_helper.sh: unexpected argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ "${CODEX_WRAP_DISABLE_RAG:-0}" = "1" ] || [ "${LLM_GATEWAY_DISABLE_RAG:-0}" = "1" ]; then
  exit 0
fi

if [ ! -t 0 ]; then
  QUERY="$(cat)"
else
  QUERY=""
fi

if [ -z "${QUERY//[[:space:]]/}" ]; then
  exit 0
fi

resolve_index_path() {
  if [ -n "${LLMC_RAG_INDEX_PATH:-}" ] && [ -f "$LLMC_RAG_INDEX_PATH" ]; then
    printf '%s\n' "$LLMC_RAG_INDEX_PATH"
    return 0
  fi
  local candidate
  candidate="$REPO_ROOT/.llmc/.rag/index_v2.db"
  if [ -f "$candidate" ]; then
    printf '%s\n' "$candidate"
    return 0
  fi
  candidate="$REPO_ROOT/.llmc/.rag/index.db"
  if [ -f "$candidate" ]; then
    printf '%s\n' "$candidate"
    return 0
  fi
  return 1
}

if [ ! -x "$SCRIPT_PATH" ]; then
  # Allow non-executable python scripts
  if [ ! -f "$SCRIPT_PATH" ]; then
    exit 0
  fi
fi

if ! INDEX_PATH="$(resolve_index_path)"; then
  exit 0
fi

export LLMC_RAG_INDEX_PATH="$INDEX_PATH"

RESULT="$("$PYTHON_BIN" "$SCRIPT_PATH" --repo "$REPO_ROOT" --limit "${RAG_PLAN_LIMIT:-5}" --min-score "${RAG_PLAN_MIN_SCORE:-0.4}" --min-confidence "${RAG_PLAN_MIN_CONFIDENCE:-0.6}" --no-log <<<"$QUERY" 2>/dev/null || true)"

printf '%s' "$RESULT" | sed '/^[[:space:]]*$/d'
