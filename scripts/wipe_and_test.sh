#!/usr/bin/env bash
# Wipe all RAG data and logs for fresh test

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🧹 Wiping LLMC_PROD data..."
echo "Repo root: $REPO_ROOT"

# Stop any running services
echo "Stopping any running llmc-rag-service..."
pkill -f llmc-rag-service || true
sleep 2

# Wipe RAG database
if [ -d "$REPO_ROOT/.rag" ]; then
    echo "Removing .rag/ directory..."
    rm -rf "$REPO_ROOT/.rag"
fi

# Wipe logs
if [ -d "$REPO_ROOT/logs" ]; then
    echo "Removing logs/ directory..."
    rm -rf "$REPO_ROOT/logs"
fi

# Wipe Python cache
echo "Removing Python cache..."
find "$REPO_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$REPO_ROOT" -type f -name "*.pyc" -delete 2>/dev/null || true

# Recreate empty structures
echo "Creating fresh directories..."
mkdir -p "$REPO_ROOT/.rag"
mkdir -p "$REPO_ROOT/logs/failed_enrichments"

echo ""
echo "✅ Clean slate ready!"
echo ""
echo "🚀 Next steps:"
echo "   1. Check your llmc.toml config"
echo "   2. Run: scripts/llmc-rag-service --help"
echo "   3. Index a repo: cd /path/to/repo && $REPO_ROOT/scripts/llmc-rag-service"
echo ""
