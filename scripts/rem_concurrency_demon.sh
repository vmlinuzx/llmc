#!/bin/bash
# Wrapper for Concurrency Demon python script
# Ensures proper environment and python path

set -e

# Find repo root
if [ -z "$LLMC_ROOT" ]; then
    LLMC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

export LLMC_ROOT

# Ensure we have the python script
SCRIPT_DIR="$(dirname "${BASH_SOURCE[0]}")"
PY_SCRIPT="$SCRIPT_DIR/rem_concurrency_demon.py"

if [ ! -f "$PY_SCRIPT" ]; then
    # Try looking in scripts dir if running from tools symlink
    SCRIPT_DIR="$LLMC_ROOT/scripts"
    PY_SCRIPT="$SCRIPT_DIR/rem_concurrency_demon.py"
fi

if [ ! -f "$PY_SCRIPT" ]; then
    echo "Error: Could not find rem_concurrency_demon.py"
    exit 1
fi

# Execute
exec python3 "$PY_SCRIPT" "$@"
