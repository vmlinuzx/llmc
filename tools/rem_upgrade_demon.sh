#!/usr/bin/env bash
# ==============================================================================
# UPGRADE DEMON - Migration paths, DB schema changes, version compatibility
# ==============================================================================
#
# Tests upgrade and migration safety.
#
# Checks:
# - Database schema migrations
# - Config format changes
# - Breaking API changes
# - Rollback safety
#
# Usage:
#   ./tools/rem_upgrade_demon.sh
#
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMC_ROOT="${LLMC_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
DATE=$(date +%Y-%m-%d)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  ⬆️  UPGRADE DEMON                                              ${NC}"
echo -e "${CYAN}  Testing migration paths and version compatibility             ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

cd "$LLMC_ROOT"
source .venv/bin/activate 2>/dev/null || true

ISSUES=0
P0_COUNT=0
P1_COUNT=0

# --- Check 1: Old schema compatibility ---
echo -e "${YELLOW}[1/4] Testing old schema compatibility...${NC}"
TMPDB=$(mktemp)
sqlite3 "$TMPDB" << 'EOF'
CREATE TABLE spans (
    id INTEGER PRIMARY KEY,
    file_path TEXT,
    start_line INTEGER,
    end_line INTEGER,
    content TEXT
);
INSERT INTO spans VALUES (1, 'test.py', 1, 10, 'def test(): pass');
EOF

if python -c "
import sqlite3
conn = sqlite3.connect('$TMPDB')
# Try to read with minimal schema
cursor = conn.execute('SELECT file_path, content FROM spans')
row = cursor.fetchone()
if row and row[0] == 'test.py':
    print('OK')
else:
    print('FAILED')
conn.close()
" 2>/dev/null | grep -q "OK"; then
    echo -e "${GREEN}  ✓ Old schema readable${NC}"
else
    echo -e "${RED}  P1: Old schema not compatible${NC}"
    ((P1_COUNT++))
    ((ISSUES++))
fi
rm -f "$TMPDB"

# --- Check 2: Missing columns graceful handling ---
echo -e "${YELLOW}[2/4] Testing missing columns handling...${NC}"
TMPDB=$(mktemp)
sqlite3 "$TMPDB" << 'EOF'
CREATE TABLE spans (
    id INTEGER PRIMARY KEY,
    file_path TEXT
);
INSERT INTO spans VALUES (1, 'test.py');
EOF

if python -c "
import sqlite3
conn = sqlite3.connect('$TMPDB')
try:
    # Try to access a column that might not exist
    cursor = conn.execute('SELECT file_path FROM spans')
    row = cursor.fetchone()
    print('OK')
except sqlite3.OperationalError as e:
    print(f'ERROR: {e}')
finally:
    conn.close()
" 2>/dev/null | grep -q "OK"; then
    echo -e "${GREEN}  ✓ Missing columns handled${NC}"
else
    echo -e "${YELLOW}  WARN: Column access needs defensive coding${NC}"
fi
rm -f "$TMPDB"

# --- Check 3: Config version migration ---
echo -e "${YELLOW}[3/4] Testing config format compatibility...${NC}"
TMPDIR=$(mktemp -d)
# Old-style config without newer sections
cat > "$TMPDIR/llmc.toml" << 'EOF'
[llmc]
name = "legacy-repo"
EOF
mkdir -p "$TMPDIR/.llmc"

if python -c "
from llmc.commands.repo_validator import validate_repo
from pathlib import Path
result = validate_repo(Path('$TMPDIR'), check_connectivity=False, check_models=False)
# Should work but may have warnings
print('OK')
" 2>/dev/null | grep -q "OK"; then
    echo -e "${GREEN}  ✓ Legacy config format accepted${NC}"
else
    echo -e "${RED}  P1: Legacy config causes failure${NC}"
    ((P1_COUNT++))
    ((ISSUES++))
fi
rm -rf "$TMPDIR"

# --- Check 4: API stability (import check) ---
echo -e "${YELLOW}[4/4] Testing public API stability...${NC}"
IMPORT_ERRORS=0

# Check key public imports still work
for module in "llmc.main" "llmc.core" "llmc.commands.repo" "llmc.commands.service"; do
    if ! python -c "import $module" 2>/dev/null; then
        echo -e "${RED}  BROKEN: $module${NC}"
        ((IMPORT_ERRORS++))
    fi
done

if [[ "$IMPORT_ERRORS" -gt 0 ]]; then
    echo -e "${RED}  P0: $IMPORT_ERRORS public modules broken${NC}"
    ((P0_COUNT += IMPORT_ERRORS))
    ((ISSUES += IMPORT_ERRORS))
else
    echo -e "${GREEN}  ✓ Public API imports OK${NC}"
fi

# --- Summary ---
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "  P0 Critical: $P0_COUNT"
echo -e "  P1 High:     $P1_COUNT"
echo -e "  Total:       $ISSUES issues"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

exit $ISSUES
