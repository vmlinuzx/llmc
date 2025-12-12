#!/bin/bash
# LLMC Quick Install Script
# Usage: curl -sSL https://raw.githubusercontent.com/vmlinuzx/llmc/main/install.sh | bash

set -e

echo "🚀 Installing LLMC..."

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo $PY_VERSION | cut -d. -f1)
PY_MINOR=$(echo $PY_VERSION | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]); then
    echo "❌ Python 3.9+ required, found $PY_VERSION"
    exit 1
fi

echo "✓ Python $PY_VERSION detected"

# Install from git
echo "📦 Installing from GitHub..."
pip install --user "git+https://github.com/vmlinuzx/llmc.git#egg=llmcwrapper[rag,tui,agent]"

# Verify installation
if command -v llmc-cli &> /dev/null; then
    echo ""
    echo "✅ LLMC installed successfully!"
    echo ""
    echo "Quick start:"
    echo "  cd /path/to/your/repo"
    echo "  llmc-cli repo register ."
    echo "  llmc-cli search 'how does auth work?'"
    echo ""
else
    echo ""
    echo "⚠️  Installed but 'llmc-cli' not in PATH."
    echo "   Try: ~/.local/bin/llmc-cli --help"
    echo "   Or add ~/.local/bin to your PATH"
fi
