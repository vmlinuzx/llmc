#!/usr/bin/env bash
set -e

# Default to current directory if LLMC_ROOT not set
export LLMC_ROOT="${LLMC_ROOT:-$(pwd)}"

# Navigate to root
cd "${LLMC_ROOT}"

if [ ! -f "tools/performance_demon.py" ]; then
    echo "Error: tools/performance_demon.py not found in ${LLMC_ROOT}"
    exit 1
fi

echo "Running Performance Demon..."
echo "Target: ${LLMC_ROOT}"

# Run the python script
# We assume python3 is available and has dependencies installed
python3 tools/performance_demon.py
