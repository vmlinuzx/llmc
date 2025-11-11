#!/usr/bin/env bash
# Pre-commit Guardrails - Step 3: Repo Cleanup
# Enforces guardrails against regression
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

log_error() { echo -e "${RED}❌ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }

echo "🛡️  Pre-commit Guardrails Check"
echo "================================="

EXIT_CODE=0

# Guardrail 1: Forbid rag_plan_snippet outside gateway
echo "🔍 Checking for RAG logic outside gateway..."
RAG_OUTSIDE_GATEWAY=$(find "$REPO_ROOT/scripts" -name "*.sh" -o -name "*.py" | grep -v "llm_gateway\|rag_plan_helper\|inventory_scanner\|pre-commit-guardrails" | xargs grep -l "attachRagPlan\|ragPlanSnippet" 2>/dev/null || true)

if [ -n "$RAG_OUTSIDE_GATEWAY" ]; then
    log_error "RAG logic found outside gateway:"
    echo "$RAG_OUTSIDE_GATEWAY" | sed 's/^/  /'
    echo ""
    log_error "Only llm_gateway.js and rag_plan_helper.sh should contain RAG logic!"
    EXIT_CODE=1
else
    log_success "No RAG logic found outside gateway"
fi

# Guardrail 2: Forbid 2>/dev/null in wrapper scripts
echo ""
echo "🔍 Checking for suppressions in wrapper scripts..."
SUPPRESSIONS_IN_WRAPPERS=$(find "$REPO_ROOT/scripts" -name "*wrap*.sh" -o -name "*cli*.sh" | xargs grep -n "2>/dev/null" 2>/dev/null || true)

if [ -n "$SUPPRESSIONS_IN_WRAPPERS" ]; then
    log_error "Suppressions found in wrapper scripts:"
    echo "$SUPPRESSIONS_IN_WRAPPERS" | sed 's/^/  /'
    echo ""
    log_error "Wrapper scripts should not hide errors with 2>/dev/null"
    EXIT_CODE=1
else
    log_success "No suppressions found in wrapper scripts"
fi

# Guardrail 3: Warn on new shell wrappers
echo ""
echo "🔍 Checking for new shell wrapper patterns..."
NEW_WRAPPER_PATTERNS=$(find "$REPO_ROOT/scripts" -name "*.sh" -newer "$REPO_ROOT/scripts/llm_gateway.sh" 2>/dev/null | head -10 || true)

if [ -n "$NEW_WRAPPER_PATTERNS" ]; then
    log_warning "New shell scripts detected (created after llm_gateway.sh):"
    echo "$NEW_WRAPPER_PATTERNS" | sed 's/^/  /'
    echo ""
    log_warning "Consider using the unified CLI (llmc) instead of new wrapper scripts"
fi

# Check for duplicate files by name
echo ""
echo "🔍 Checking for duplicate filenames..."
DUPLICATE_NAMES=$(find "$REPO_ROOT/scripts" -name "*.sh" -o -name "*.py" | sed 's|.*/||' | sort | uniq -d)

if [ -n "$DUPLICATE_NAMES" ]; then
    log_warning "Duplicate filenames found:"
    echo "$DUPLICATE_NAMES" | sed 's/^/  /'
    echo ""
fi

# Check if .trash/attic exists
echo ""
echo "🔍 Checking attic status..."
if [ ! -d "$REPO_ROOT/.trash" ]; then
    log_warning "No .trash/attic folder found - creating..."
    mkdir -p "$REPO_ROOT/.trash"
    log_success "Created .trash/attic folder"
fi

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    log_success "All guardrails passed!"
else
    log_error "Guardrails failed! Please fix the issues above."
fi

exit $EXIT_CODE