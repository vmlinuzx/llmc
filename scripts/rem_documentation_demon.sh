#!/bin/bash
set -e

# Resolve repo root
# If this script is a symlink, we need to resolve it
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
DIR="$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )"

# Assuming script is in scripts/ or tools/ and repo root is one level up?
# If in scripts/ (tracked), root is ../
# If in tools/ (symlinked), real path is scripts/, so root is ../

REPO_ROOT="$(dirname "$DIR")"

# Allow override
if [ -z "$LLMC_ROOT" ]; then
    export LLMC_ROOT="$REPO_ROOT"
fi

cd "$LLMC_ROOT"

# Add root to PYTHONPATH so we can import llmc and scripts
export PYTHONPATH="$LLMC_ROOT:$PYTHONPATH"

# Run the demon
# We execute the python script located in scripts/doc_demon.py
# If the wrapper is in tools/ (symlink), we still want to point to scripts/doc_demon.py
# But if we are running from the resolved location, it's in the same dir as this script (if it's in scripts/)

python3 "$DIR/doc_demon.py" "$@"
