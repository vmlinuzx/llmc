#!/bin/bash

# Make all shell scripts in the template executable
# Usage: ./fix_executable_permissions.sh [path_to_template]

TEMPLATE_DIR=${1:-llmc_template}

if [ ! -d "$TEMPLATE_DIR" ]; then
    echo "❌ Template directory '$TEMPLATE_DIR' not found!"
    echo "Usage: $0 [template_directory]"
    exit 1
fi

echo "🔧 Making scripts executable in: $TEMPLATE_DIR"

# Find and make all shell scripts executable
find "$TEMPLATE_DIR" -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true
find "$TEMPLATE_DIR" -name "deploy.py" -exec chmod +x {} \; 2>/dev/null || true

# Also make any python scripts executable if they have shebangs
find "$TEMPLATE_DIR" -name "*.py" -exec grep -l "^#!/usr/bin/env python" {} \; -exec chmod +x {} \; 2>/dev/null || true

echo "✅ Made scripts executable!"

# List what we changed
echo "📝 Made executable:"
find "$TEMPLATE_DIR" -type f \( -name "*.sh" -o -name "deploy.py" -o -name "*.py" \) -exec ls -la {} \; | grep "rwx" | head -10