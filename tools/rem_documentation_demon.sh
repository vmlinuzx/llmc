#!/bin/bash
LLMC_ROOT="${LLMC_ROOT:-$(pwd)}"
cd "$LLMC_ROOT"
export PYTHONPATH=$PYTHONPATH:.
python3 tools/doc_demon.py "$@"
