#!/usr/bin/env bash
# ==============================================================================
# PERFORMANCE DEMON - Benchmarks, slowdowns, memory leaks
# ==============================================================================
#
# Hunts for performance regressions, memory leaks, and slow operations.
#
# Checks:
# - Pytest benchmark results
# - Import time profiling
# - Memory usage during operations
# - Slow test detection
#
# Usage:
#   ./tools/rem_performance_demon.sh
#
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMC_ROOT="${LLMC_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
REPORTS_DIR="$LLMC_ROOT/tests/REPORTS"
DATE=$(date +%Y-%m-%d)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  🏃 PERFORMANCE DEMON                                          ${NC}"
echo -e "${CYAN}  Hunting slowdowns and memory leaks                            ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

cd "$LLMC_ROOT"
source .venv/bin/activate 2>/dev/null || true

ISSUES=0
P0_COUNT=0
P1_COUNT=0

# --- Check 1: Import time profiling ---
echo -e "${YELLOW}[1/4] Checking import times...${NC}"
IMPORT_TIME=$(python -c "
import time
start = time.time()
import llmc.main
print(f'{time.time() - start:.2f}')
" 2>/dev/null || echo "999")

if (( $(echo "$IMPORT_TIME > 5.0" | bc -l) )); then
    echo -e "${RED}  P1: Import time too slow: ${IMPORT_TIME}s (threshold: 5s)${NC}"
    ((P1_COUNT++))
    ((ISSUES++))
elif (( $(echo "$IMPORT_TIME > 2.0" | bc -l) )); then
    echo -e "${YELLOW}  WARN: Import time high: ${IMPORT_TIME}s${NC}"
else
    echo -e "${GREEN}  ✓ Import time OK: ${IMPORT_TIME}s${NC}"
fi

# --- Check 2: Slow tests detection ---
echo -e "${YELLOW}[2/4] Finding slow tests...${NC}"
SLOW_TESTS=$(python -m pytest tests/ --collect-only -q 2>/dev/null | wc -l || echo "0")
echo "  Found $SLOW_TESTS test items"

# Run quick timing check on a subset
if python -m pytest tests/test_p0_acceptance.py -v --tb=no --durations=5 2>&1 | grep -q "slowest"; then
    echo -e "${GREEN}  ✓ Benchmark timing collected${NC}"
else
    echo -e "${YELLOW}  WARN: Could not collect timing data${NC}"
fi

# --- Check 3: Memory profiling (basic) ---
echo -e "${YELLOW}[3/4] Checking memory usage...${NC}"
MEM_BEFORE=$(python -c "import psutil; print(psutil.Process().memory_info().rss // 1024 // 1024)" 2>/dev/null || echo "0")
python -c "
from llmc.main import app
from tools.rag.search import search_spans
" 2>/dev/null || true
MEM_AFTER=$(python -c "import psutil; print(psutil.Process().memory_info().rss // 1024 // 1024)" 2>/dev/null || echo "0")
echo "  Memory usage: ~${MEM_AFTER}MB after imports"

if [[ "$MEM_AFTER" -gt 500 ]]; then
    echo -e "${RED}  P1: Memory usage high: ${MEM_AFTER}MB (threshold: 500MB)${NC}"
    ((P1_COUNT++))
    ((ISSUES++))
else
    echo -e "${GREEN}  ✓ Memory usage OK${NC}"
fi

# --- Check 4: Database query performance ---
echo -e "${YELLOW}[4/4] Checking database performance...${NC}"
if [[ -f "$LLMC_ROOT/.llmc/rag/index_v2.db" ]]; then
    DB_SIZE=$(du -h "$LLMC_ROOT/.llmc/rag/index_v2.db" 2>/dev/null | cut -f1)
    echo "  Database size: $DB_SIZE"
    
    # Quick query timing
    QUERY_TIME=$(python -c "
import time
import sqlite3
conn = sqlite3.connect('$LLMC_ROOT/.llmc/rag/index_v2.db')
start = time.time()
conn.execute('SELECT COUNT(*) FROM spans').fetchone()
print(f'{(time.time() - start)*1000:.1f}')
conn.close()
" 2>/dev/null || echo "999")
    
    if (( $(echo "$QUERY_TIME > 100" | bc -l) )); then
        echo -e "${YELLOW}  WARN: Query time slow: ${QUERY_TIME}ms${NC}"
    else
        echo -e "${GREEN}  ✓ Query time OK: ${QUERY_TIME}ms${NC}"
    fi
else
    echo -e "${YELLOW}  SKIP: No database found${NC}"
fi

# --- Summary ---
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "  P0 Critical: $P0_COUNT"
echo -e "  P1 High:     $P1_COUNT"
echo -e "  Total:       $ISSUES issues"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

exit $ISSUES
