#!/usr/bin/env bash
# ==============================================================================
# Migrate Old Reports to Archive
# ==============================================================================
# 
# One-time migration script to clean up the sprawling tests/REPORTS/ directory.
# Moves all existing reports to tests/REPORTS/archive/ and sets up the new
# current/previous structure.
#
# Usage:
#   ./thunderdome/scripts/migrate_reports.sh [--dry-run]
#
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORTS_DIR="$REPO_ROOT/tests/REPORTS"

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "=== DRY RUN MODE ==="
    echo ""
fi

echo "Migrating reports in: $REPORTS_DIR"
echo ""

# Create new structure
if [[ "$DRY_RUN" == false ]]; then
    mkdir -p "$REPORTS_DIR/current"
    mkdir -p "$REPORTS_DIR/previous"
    mkdir -p "$REPORTS_DIR/archive"
fi

# Count files to migrate
file_count=$(find "$REPORTS_DIR" -maxdepth 1 -type f | wc -l)
echo "Found $file_count files to archive"

# Move all files (not directories) from root of REPORTS to archive
if [[ "$DRY_RUN" == true ]]; then
    echo ""
    echo "Would move the following to archive/:"
    find "$REPORTS_DIR" -maxdepth 1 -type f -exec basename {} \; | head -20
    remaining=$((file_count - 20))
    if [[ $remaining -gt 0 ]]; then
        echo "... and $remaining more files"
    fi
else
    find "$REPORTS_DIR" -maxdepth 1 -type f -exec mv {} "$REPORTS_DIR/archive/" \;
    echo "Moved $file_count files to archive/"
fi

# Handle mcp subdirectory if it exists
if [[ -d "$REPORTS_DIR/mcp" ]]; then
    mcp_count=$(find "$REPORTS_DIR/mcp" -type f | wc -l)
    echo "Found $mcp_count files in mcp/ subdirectory"
    
    if [[ "$DRY_RUN" == true ]]; then
        echo "Would move mcp/ to archive/mcp/"
    else
        mv "$REPORTS_DIR/mcp" "$REPORTS_DIR/archive/"
        echo "Moved mcp/ to archive/"
    fi
fi

echo ""
echo "New structure:"
if [[ "$DRY_RUN" == false ]]; then
    tree -L 2 "$REPORTS_DIR" 2>/dev/null || ls -la "$REPORTS_DIR"
else
    echo "  tests/REPORTS/"
    echo "  ├── archive/     (all old reports)"
    echo "  ├── current/     (active test run)"
    echo "  └── previous/    (one generation back)"
fi

echo ""
echo "Done! Old reports preserved in archive/, new runs go to current/"
