#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

echo "[indexenrich-azure] Repo root: $REPO_ROOT"

if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import importlib
import os
import sys

required_modules = ("tree_sitter", "tree_sitter_languages")
for module in required_modules:
    try:
        importlib.import_module(module)
    except ModuleNotFoundError:
        sys.exit(1)
PY
then
  echo "[indexenrich-azure] Missing tree_sitter dependencies." >&2
  echo "Run: $PYTHON_BIN -m pip install -r tools/rag/requirements.txt" >&2
  exit 1
fi

env_file="$REPO_ROOT/.env.local"
if [[ -f "$env_file" ]]; then
  echo "[indexenrich-azure] Loading env from $env_file"
  set -a
  # shellcheck disable=SC1090
  source "$env_file"
  set +a
fi

missing_env=()
for var in AZURE_OPENAI_ENDPOINT AZURE_OPENAI_KEY AZURE_OPENAI_DEPLOYMENT; do
  if [[ -z "${!var:-}" ]]; then
    missing_env+=("$var")
  fi
done

if ((${#missing_env[@]})); then
  echo "[indexenrich-azure] Missing required Azure environment variables: ${missing_env[*]}" >&2
  exit 1
fi

sync_args=()
for relative in "docs/preprocessor_flow.md" "DOCS/preprocessor_flow.md"; do
  if [[ -f "$REPO_ROOT/$relative" ]]; then
    sync_args+=("--path" "$relative")
  fi
done

if ((${#sync_args[@]})); then
  echo "[indexenrich-azure] Syncing spans: ${sync_args[*]}"
  "$PYTHON_BIN" -m tools.rag.cli sync "${sync_args[@]}"
else
  echo "[indexenrich-azure] No documented paths found to sync." >&2
fi

echo "[indexenrich-azure] Updating enrichment metadata via Azure"
LLM_DISABLED=false NEXT_PUBLIC_LLM_DISABLED=false LLM_GATEWAY_DISABLE_LOCAL=1 \
  "$PYTHON_BIN" "$REPO_ROOT/scripts/qwen_enrich_batch.py" \
    --repo "$REPO_ROOT" \
    --backend gateway \
    --api \
    --batch-size 5 \
    --max-spans 0

echo "[indexenrich-azure] Regenerating embeddings for any new spans"
"$PYTHON_BIN" -m tools.rag.cli embed --execute --limit 100

echo "[indexenrich-azure] Current RAG stats"
"$PYTHON_BIN" -m tools.rag.cli stats
