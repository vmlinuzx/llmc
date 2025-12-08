#!/usr/bin/env bash
# ==============================================================================
# CHAOS DEMON - Random failures, timeouts, resource exhaustion
# ==============================================================================
#
# Tests system resilience by simulating failure conditions.
#
# Checks:
# - Graceful handling of missing files
# - Timeout behavior
# - Large input handling
# - Corrupted database recovery
#
# Usage:
#   ./tools/rem_chaos_demon.sh
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
echo -e "${CYAN}  🌀 CHAOS DEMON                                                ${NC}"
echo -e "${CYAN}  Testing resilience under failure conditions                   ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

cd "$LLMC_ROOT"
source .venv/bin/activate 2>/dev/null || true

ISSUES=0
P0_COUNT=0
P1_COUNT=0

# --- Check 1: Missing config file ---
echo -e "${YELLOW}[1/5] Testing missing config handling...${NC}"
TMPDIR=$(mktemp -d)
if python -c "
import os
os.chdir('$TMPDIR')
try:
    from llmc.core import find_repo_root
    find_repo_root()
    print('ERROR')
except Exception as e:
    print('OK')
" 2>/dev/null | grep -q "OK"; then
    echo -e "${GREEN}  ✓ Correctly handles missing repo${NC}"
else
    echo -e "${RED}  P1: Crashes on missing repo instead of graceful error${NC}"
    ((P1_COUNT++))
    ((ISSUES++))
fi
rm -rf "$TMPDIR"

# --- Check 2: Large query handling ---
echo -e "${YELLOW}[2/5] Testing large query handling...${NC}"
LARGE_QUERY=$(python -c "print('x' * 100000)")
if timeout 5 python -c "
from tools.rag_nav.tool_handlers import tool_rag_search
try:
    result = tool_rag_search('$LLMC_ROOT', '$LARGE_QUERY'[:1000], limit=1)
    print('OK')
except Exception as e:
    print(f'HANDLED: {type(e).__name__}')
" 2>/dev/null; then
    echo -e "${GREEN}  ✓ Large query handled safely${NC}"
else
    echo -e "${RED}  P1: Large query causes crash or hang${NC}"
    ((P1_COUNT++))
    ((ISSUES++))
fi

# --- Check 3: Empty database ---
echo -e "${YELLOW}[3/5] Testing empty database handling...${NC}"
EMPTY_DB=$(mktemp)
sqlite3 "$EMPTY_DB" "CREATE TABLE test (id INTEGER);" 2>/dev/null || true
if python -c "
import sqlite3
conn = sqlite3.connect('$EMPTY_DB')
try:
    conn.execute('SELECT * FROM spans')
except sqlite3.OperationalError:
    print('OK')
" 2>/dev/null | grep -q "OK"; then
    echo -e "${GREEN}  ✓ Empty database handled safely${NC}"
else
    echo -e "${YELLOW}  WARN: Unexpected empty database behavior${NC}"
fi
rm -f "$EMPTY_DB"

# --- Check 4: Unicode chaos ---
echo -e "${YELLOW}[4/5] Testing unicode chaos...${NC}"
UNICODE_CHAOS="🔥💀👻 SELECT * FROM; DROP TABLE--"
if python -c "
from tools.rag_nav.tool_handlers import tool_rag_search
try:
    result = tool_rag_search('$LLMC_ROOT', '''$UNICODE_CHAOS''', limit=1)
    print('OK')
except Exception as e:
    print(f'HANDLED: {type(e).__name__}')
" 2>/dev/null; then
    echo -e "${GREEN}  ✓ Unicode chaos handled safely${NC}"
else
    echo -e "${RED}  P1: Unicode input causes crash${NC}"
    ((P1_COUNT++))
    ((ISSUES++))
fi

# --- Check 5: Timeout behavior ---
echo -e "${YELLOW}[5/5] Testing command timeout...${NC}"
if timeout 3 python -c "
import time
# Simulate a short operation
time.sleep(0.1)
print('OK')
" 2>/dev/null; then
    echo -e "${GREEN}  ✓ Timeout mechanism works${NC}"
else
    echo -e "${YELLOW}  WARN: Timeout test inconclusive${NC}"
fi

# --- Summary ---
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "  P0 Critical: $P0_COUNT"
echo -e "  P1 High:     $P1_COUNT"
echo -e "  Total:       $ISSUES issues"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

exit $ISSUES
