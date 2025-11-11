#!/usr/bin/env bash
# Tail codex gateway log
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
tail -f logs/codexlog.txt
