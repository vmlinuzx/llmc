#!/usr/bin/env bash
# Watch planner metrics summary every 10 seconds
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
watch -n 10 "$SCRIPT_DIR/summarize_planner_metrics.py"
