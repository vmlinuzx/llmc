#!/bin/bash
set -e

# Upgrade Demon - Version Migration Testing
# Usage: LLMC_ROOT=/path/to/repo ./scripts/rem_upgrade_demon.sh
# (or ./tools/rem_upgrade_demon.sh if symlinked)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

LLMC_ROOT="${LLMC_ROOT:-$(pwd)}"
# Resolve absolute path
LLMC_ROOT=$(cd "$LLMC_ROOT" && pwd)

# Determine location of this script and migration scripts
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# Handle symlink resolution (basic check)
if [[ "$SCRIPT_DIR" == */tools ]]; then
    MIGRATION_DIR="$SCRIPT_DIR/../scripts"
else
    MIGRATION_DIR="$SCRIPT_DIR"
fi

# Ensure PYTHONPATH includes the repo root of the tool
TOOL_REPO_ROOT=$(dirname "$MIGRATION_DIR")
export PYTHONPATH="$TOOL_REPO_ROOT:$PYTHONPATH"

echo -e "${YELLOW}Running Upgrade Demon on: $LLMC_ROOT${NC}"

# 1. DB Migration
echo -e "\n${YELLOW}=== 1. DB Migration Check ===${NC}"
MIGRATION_SCRIPTS=$(find "$MIGRATION_DIR" -maxdepth 1 -name "migrate_*.py")

if [ -z "$MIGRATION_SCRIPTS" ]; then
    echo "No migration scripts found in $MIGRATION_DIR"
else
    for script in $MIGRATION_SCRIPTS; do
        echo "Running migration script: $(basename "$script")"
        if python3 "$script" "$LLMC_ROOT"; then
            echo -e "${GREEN}✓ Migration success: $(basename "$script")${NC}"
        else
            echo -e "${RED}✗ Migration failed: $(basename "$script")${NC}"
            exit 1
        fi
    done
fi

# 2. Config Migration
echo -e "\n${YELLOW}=== 2. Config Migration Check ===${NC}"
# Use module invocation to avoid path issues
if python3 -m llmc repo validate "$LLMC_ROOT" --no-connectivity; then
    echo -e "${GREEN}✓ Config validation passed${NC}"
else
    echo -e "${RED}✗ Config validation failed${NC}"
    exit 1
fi

# 3. Breaking Changes
echo -e "\n${YELLOW}=== 3. Breaking Changes Check ===${NC}"
echo "Scanning for internal usage of deprecated APIs (grep)..."
# Check for @deprecated or DeprecationWarning usage in the codebase
DEPRECATED_COUNT=$(grep -r "deprecated" "$LLMC_ROOT/llmc" "$LLMC_ROOT/scripts" 2>/dev/null | grep -v "rem_upgrade_demon.sh" | wc -l)

if [ "$DEPRECATED_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}⚠ Found $DEPRECATED_COUNT occurrences of 'deprecated' in codebase.${NC}"
    # We don't fail, just warn.
else
    echo -e "${GREEN}✓ No explicit deprecation markers found.${NC}"
fi

# 4. Backwards Compatibility
echo -e "\n${YELLOW}=== 4. Backwards Compatibility Check ===${NC}"
echo "Verifying data readability..."
# We need to run stats in the repo root
(
    cd "$LLMC_ROOT"
    if python3 -m llmc.rag.cli stats; then
         echo -e "${GREEN}✓ RAG Index is readable${NC}"
    else
         echo -e "${RED}✗ RAG Index read failed${NC}"
         exit 1
    fi
)

# 5. Rollback Safety
echo -e "\n${YELLOW}=== 5. Rollback Safety Check ===${NC}"
echo "Searching for rollback scripts..."
ROLLBACK_SCRIPTS=$(find "$MIGRATION_DIR" -maxdepth 1 -name "rollback_*.py")
if [ -z "$ROLLBACK_SCRIPTS" ]; then
    echo -e "${YELLOW}⚠ No automated rollback scripts found.${NC}"
    echo "Manual rollback verification required."
else
    echo -e "${GREEN}✓ Found rollback scripts: $ROLLBACK_SCRIPTS${NC}"
    # In a real scenario, we would test running them.
fi

echo -e "\n${GREEN}=== Upgrade Test Complete ===${NC}"
