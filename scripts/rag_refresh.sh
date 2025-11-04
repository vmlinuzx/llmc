#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-}"

if [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
elif [ -n "${RAG_VENV:-}" ] && [ -x "$RAG_VENV/bin/python" ]; then
  PYTHON_BIN="$RAG_VENV/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

RAG_INDEX_PATH="${LLMC_RAG_INDEX_PATH:-$ROOT/.rag/index_v2.db}"
if [ ! -f "$RAG_INDEX_PATH" ] && [ -f "$ROOT/.rag/index.db" ]; then
  RAG_INDEX_PATH="$ROOT/.rag/index.db"
fi

if [ ! -f "$RAG_INDEX_PATH" ]; then
  echo "[rag-refresh] No RAG index present; run ./scripts/indexenrich.sh first." >&2
  exit 1
fi

export LLMC_RAG_INDEX_PATH="$RAG_INDEX_PATH"

CHANGED=()
while IFS= read -r line; do
  path="${line:3}"
  if [[ "$path" == *" -> "* ]]; then
    path="${path##* -> }"
  fi
  CHANGED+=("$path")
done < <(cd "$ROOT" && git status --porcelain --untracked-files=no)

if [ "${#CHANGED[@]}" -eq 0 ]; then
  echo "[rag-refresh] No tracked changes detected; skipping sync."
else
  echo "[rag-refresh] Syncing ${#CHANGED[@]} paths"
  "$ROOT/scripts/rag_sync.sh" "${CHANGED[@]}"
fi

echo "[rag-refresh] Enrichment pass"
LLM_DISABLED=false NEXT_PUBLIC_LLM_DISABLED=false \
  "$PYTHON_BIN" "$ROOT/scripts/qwen_enrich_batch.py" \
  --repo "$ROOT" \
  --backend ollama \
  --batch-size "${RAG_REFRESH_BATCH_SIZE:-5}" \
  --max-spans "${RAG_REFRESH_MAX_SPANS:-0}" \
  --cooldown "${RAG_REFRESH_COOLDOWN:-300}"

echo "[rag-refresh] Embedding refresh"
"$PYTHON_BIN" -m tools.rag.cli embed --execute --limit "${RAG_REFRESH_EMBED_LIMIT:-100}"

echo "[rag-refresh] Current stats"
"$PYTHON_BIN" -m tools.rag.cli stats

echo "[rag-refresh] Done"
