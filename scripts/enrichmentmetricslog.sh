#!/usr/bin/env bash
# Watch enrichment metrics roll-up every 10 seconds
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
watch -n 10 "$SCRIPT_DIR/summarize_enrichment_metrics.py"
