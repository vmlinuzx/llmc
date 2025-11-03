#!/usr/bin/env bash
# Tail enrichment metrics JSONL for live entries
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
tail -f logs/enrichment_metrics.jsonl
