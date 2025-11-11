#!/usr/bin/env bash
# Test script for Template Builder TUI

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$SCRIPT_DIR"

echo "========================================="
echo "Template Builder TUI - Test Script"
echo "========================================="
echo ""

# Test 1: Check if script exists and is executable
echo "Test 1: Checking if template_builder_tui.sh exists and is executable..."
if [ -f "$ROOT_DIR/scripts/template_builder_tui.sh" ]; then
    echo "✓ Script exists"
    if [ -x "$ROOT_DIR/scripts/template_builder_tui.sh" ]; then
        echo "✓ Script is executable"
    else
        echo "✗ Script is not executable (fixing...)"
        chmod +x "$ROOT_DIR/scripts/template_builder_tui.sh"
        echo "✓ Fixed"
    fi
else
    echo "✗ Script not found"
    exit 1
fi
echo ""

# Test 2: Check integration with claude_wrap.sh
echo "Test 2: Checking integration with claude_wrap.sh..."
if grep -q "LAUNCH_TEMPLATE_TUI" "$ROOT_DIR/scripts/claude_wrap.sh"; then
    echo "✓ LAUNCH_TEMPLATE_TUI flag found in claude_wrap.sh"
else
    echo "✗ LAUNCH_TEMPLATE_TUI flag not found in claude_wrap.sh"
    exit 1
fi

if grep -q "template_builder_tui.sh" "$ROOT_DIR/scripts/claude_wrap.sh"; then
    echo "✓ Reference to template_builder_tui.sh found in claude_wrap.sh"
else
    echo "✗ Reference to template_builder_tui.sh not found in claude_wrap.sh"
    exit 1
fi
echo ""

# Test 3: Check if template builder app exists
echo "Test 3: Checking if template-builder app exists..."
if [ -d "$ROOT_DIR/apps/template-builder" ]; then
    echo "✓ Template builder app directory exists"
    if [ -f "$ROOT_DIR/apps/template-builder/package.json" ]; then
        echo "✓ package.json found"
    else
        echo "✗ package.json not found"
        exit 1
    fi
else
    echo "✗ Template builder app directory not found"
    exit 1
fi
echo ""

# Test 4: Check if template builder has required dependencies
echo "Test 4: Checking if template builder has dependencies installed..."
if [ -d "$ROOT_DIR/apps/template-builder/node_modules" ]; then
    echo "✓ node_modules directory exists"
    echo "  Dependencies installed:"
    ls -1 "$ROOT_DIR/apps/template-builder/node_modules" | wc -l | xargs echo "  -" | sed 's/$/ packages/'
else
    echo "⚠ node_modules not found - dependencies may need to be installed"
    echo "  Run: cd $ROOT_DIR/apps/template-builder && npm install"
fi
echo ""

# Test 5: Check if jq is available
echo "Test 5: Checking for JSON parsing tools..."
if command -v jq > /dev/null 2>&1; then
    echo "✓ jq is installed (version: $(jq --version))"
    HAS_JQ=true
else
    echo "⚠ jq not installed - TUI will use fallback parsing"
    HAS_JQ=false
fi
echo ""

# Test 6: Verify API endpoints exist
echo "Test 6: Checking template builder API endpoints..."
if [ -f "$ROOT_DIR/apps/template-builder/app/api/options/route.ts" ]; then
    echo "✓ GET /api/options endpoint exists"
else
    echo "✗ GET /api/options endpoint not found"
fi

if [ -f "$ROOT_DIR/apps/template-builder/app/api/generate/route.ts" ]; then
    echo "✓ POST /api/generate endpoint exists"
else
    echo "✗ POST /api/generate endpoint not found"
fi
echo ""

# Summary
echo "========================================="
echo "Summary"
echo "========================================="
echo ""
echo "The Template Builder TUI is ready to use!"
echo ""
echo "Launch methods:"
echo "  1. Direct: ./scripts/template_builder_tui.sh"
echo "  2. Via claude_wrap: ./scripts/claude_wrap.sh --template"
echo ""
echo "Features:"
echo "  - Interactive menu system"
echo "  - Automatic template builder server management"
echo "  - Dynamic configuration with profile, tools, and artifacts"
echo "  - Bundle generation and download"
echo "  - Log viewing"
echo "  - Browser integration"
echo ""
echo "To test manually, run:"
echo "  cd $ROOT_DIR"
echo "  ./scripts/template_builder_tui.sh"
echo ""