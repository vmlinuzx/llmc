#!/bin/bash
# bootstrap.sh - Initial setup script

set -e

# This script has hardcoded paths that should be adjusted
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LLMC_ROOT="$SCRIPT_DIR"

# These paths should be adjusted during deployment
TOOLS_DIR="$LLMC_ROOT/tools"
CONFIG_DIR="$LLMC_ROOT/config"
SCRIPTS_DIR="$LLMC_ROOT/scripts"

echo "LLMC Bootstrap"
echo "=============="
echo "Tools directory: $TOOLS_DIR"
echo "Config directory: $CONFIG_DIR"
echo "Scripts directory: $SCRIPTS_DIR"

# Create necessary directories
mkdir -p "$TOOLS_DIR/rag"
mkdir -p "$CONFIG_DIR/profiles"
