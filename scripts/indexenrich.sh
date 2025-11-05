#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

FORCE_NANO=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force-nano)
      FORCE_NANO=1
      shift
      ;;
    *)
      echo "Usage: $0 [--force-nano]" >&2
      exit 1
      ;;
  esac
done

if [ "$FORCE_NANO" -eq 1 ]; then
  echo "[indexenrich] Forcing nano tier via gateway backend"
  ENRICH_BACKEND="gateway"
  ENRICH_ROUTER="on"
  ENRICH_START_TIER="nano"
else
  ENRICH_BACKEND="ollama"
  ENRICH_ROUTER="off"
  ENRICH_START_TIER="7b"
fi

echo "[indexenrich] Repo root: $REPO_ROOT"

if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import importlib
import sys
for module in ("tree_sitter", "tree_sitter_languages"):
    try:
        importlib.import_module(module)
    except ModuleNotFoundError:
        sys.exit(1)
PY
then
  echo "[indexenrich] Missing tree_sitter dependencies." >&2
  echo "Run: $PYTHON_BIN -m pip install -r tools/rag/requirements.txt" >&2
  exit 1
fi

sync_args=()
for relative in "DOCS/preprocessor_flow.md" "DOCS/archive/preprocessor_flow_legacy.md"; do
  if [[ -f "$REPO_ROOT/$relative" ]]; then
    sync_args+=("--path" "$relative")
  fi
done

if ((${#sync_args[@]})); then
  echo "[indexenrich] Syncing spans: ${sync_args[*]}"
  "$PYTHON_BIN" -m tools.rag.cli sync "${sync_args[@]}"
else
  echo "[indexenrich] No documented paths found to sync." >&2
fi

echo "[indexenrich] Updating enrichment metadata"
LLM_DISABLED=false NEXT_PUBLIC_LLM_DISABLED=false \
"$PYTHON_BIN" "$REPO_ROOT/scripts/qwen_enrich_batch.py" \
  --repo "$REPO_ROOT" \
  --backend "$ENRICH_BACKEND" \
  --batch-size 5 \
  --router "$ENRICH_ROUTER" \
  --start-tier "$ENRICH_START_TIER" \
  --max-spans 0

echo "[indexenrich] Regenerating embeddings for any new spans"
"$PYTHON_BIN" -m tools.rag.cli embed --execute --limit 100

echo "[indexenrich] Current RAG stats"
"$PYTHON_BIN" -m tools.rag.cli stats
