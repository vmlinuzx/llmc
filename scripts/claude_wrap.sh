#!/usr/bin/env bash
# claude_wrap.sh - Thin adapter for Claude via unified CLI
# Step 3: RAG logic moved to gateway, wrapper is now thin adapter
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXEC_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Thin adapter: delegate to unified CLI with --provider claude
exec "$EXEC_ROOT/llmc_cli.py" "$@" --provider claude