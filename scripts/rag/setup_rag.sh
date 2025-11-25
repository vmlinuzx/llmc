#!/usr/bin/env bash
# setup_rag.sh - One-command RAG setup

set -e

echo "🚀 DeepSeek RAG System - Quick Setup"
echo "======================================"
echo ""

cd "$(dirname "$0")"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"
echo ""

# Create venv
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate

# Install requirements
echo "📦 Installing requirements..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "✅ Requirements installed"
echo ""

# Check if already indexed
RAG_DB_DIR="${RAG_DB_DIR:-$HOME/.deepseek_rag}"
if [ -d "$RAG_DB_DIR" ]; then
    echo "📊 RAG database exists at $RAG_DB_DIR"
    python index_workspace.py --stats
    echo ""
    
    read -p "Reindex workspace? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🔄 Reindexing workspace..."
        python index_workspace.py --reindex
    fi
else
    echo "🔍 Indexing workspace for first time..."
    echo "   This will take 5-10 minutes for ~50 projects"
    echo ""
    python index_workspace.py
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "📚 Quick start commands:"
echo ""
echo "  # Search your code"
echo "  python query_context.py \"authentication\""
echo ""
echo "  # Build context for task"
echo "  python query_context.py \"add validation\" --project glideclubs --context"
echo ""
echo "  # Start web UI"
echo "  python rag_server.py"
echo "  # Visit: http://localhost:${RAG_PORT:-8765}"
echo ""
echo "  # Start file watcher (auto-reindex)"
echo "  python watch_workspace.py"
echo ""
echo "  # Use with llm_gateway (automatic!)"
echo "  cd ~/src/glideclubs"
echo "  echo \"your task\" | ./scripts/llm_gateway.sh --local"
echo ""