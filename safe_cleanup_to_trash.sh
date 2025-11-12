#!/bin/bash
# Safe cleanup: move cleanup candidates to .trash/ instead of deleting

set -e

TRASH_DIR="./.trash"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${TRASH_DIR}/cleanup_${TIMESTAMP}.log"

echo "Moving cleanup candidates to .trash/ (safe mode - nothing is deleted)"
echo "Log file: $LOG_FILE"
echo ""

# Create trash subdir for this cleanup session
mkdir -p "${TRASH_DIR}/cleanup_${TIMESTAMP}"
TRASH_SESSION="${TRASH_DIR}/cleanup_${TIMESTAMP}"

move_to_trash() {
    local src="$1"
    local desc="$2"

    if [ -e "$src" ]; then
        echo "Moving: $src -> ${TRASH_SESSION}/"
        mv -v "$src" "${TRASH_SESSION}/" 2>&1 | tee -a "$LOG_FILE"
        return 0
    else
        echo "Not found: $src"
        return 1
    fi
}

echo "=== Moving node_modules directories ==="
find . -type d -name "node_modules" -not -path "./.trash/*" | while read -r dir; do
    move_to_trash "$dir" "node_modules"
done

echo ""
echo "=== Moving cache directories ==="
for cache in "__pycache__" ".pytest_cache" ".mypy_cache" ".cache" ".tmp"; do
    find . -type d -name "$cache" -not -path "./.trash/*" | while read -r dir; do
        move_to_trash "$dir" "cache dir"
    done
done

echo ""
echo "=== Moving backup files ==="
find . -maxdepth 1 -type f \( -name "*.bak" -o -name "*~" -o -name "*.backup" \) -not -path "./.trash/*" | while read -r file; do
    move_to_trash "$file" "backup file"
done

echo ""
echo "=== Moving old zip files ==="
find . -maxdepth 1 -type f -name "*.zip" -not -path "./.trash/*" | while read -r file; do
    move_to_trash "$file" "zip file"
done

echo ""
echo "=== Cleanup Summary ==="
echo "Moved items logged to: $LOG_FILE"
echo "Trash location: ${TRASH_SESSION}/"
echo ""
echo "Contents of trash session:"
ls -lah "${TRASH_SESSION}/" 2>/dev/null || echo "(empty)"
echo ""
echo "To restore anything:"
echo "  mv ${TRASH_SESSION}/* ./"
echo ""
echo "To permanently delete (when you're sure):"
echo "  rm -rf ${TRASH_SESSION}"
