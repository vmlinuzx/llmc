#!/usr/bin/env bash
# gemini_wrap.sh - Thin adapter for Gemini via unified CLI
# Step 3: RAG logic moved to gateway, wrapper is now thin adapter
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXEC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Thin adapter: delegate to unified CLI with --provider gemini
exec "$EXEC_ROOT/llmc_cli.py" "$@" --provider gemini