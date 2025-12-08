#!/usr/bin/env bash
# ==============================================================================
# CONCURRENCY DEMON - Race conditions, deadlocks, MAASL violations
# ==============================================================================
#
# Tests multi-agent coordination and concurrency safety.
#
# Checks:
# - MAASL lock acquisition
# - Concurrent database access
# - File locking behavior
# - Deadlock detection
#
# Usage:
#   ./tools/rem_concurrency_demon.sh
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
echo -e "${CYAN}  🔄 CONCURRENCY DEMON                                          ${NC}"
echo -e "${CYAN}  Testing race conditions and deadlocks                         ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

cd "$LLMC_ROOT"
source .venv/bin/activate 2>/dev/null || true

ISSUES=0
P0_COUNT=0
P1_COUNT=0

# --- Check 1: MAASL lock file creation ---
echo -e "${YELLOW}[1/4] Testing MAASL lock file creation...${NC}"
if python -c "
from pathlib import Path
from llmc_mcp.maasl import MAASL, ResourceDescriptor

maasl = MAASL(Path('$LLMC_ROOT'))
desc = ResourceDescriptor('TEST', 'test')

# Test lock acquisition
try:
    def dummy_op():
        return 'ok'
    result = maasl.call_with_stomp_guard(
        op=dummy_op,
        resources=[desc],
        intent='test',
        mode='interactive',
        agent_id='test-agent',
        session_id='test-session'
    )
    print('OK')
except Exception as e:
    print(f'FAILED: {e}')
" 2>/dev/null | grep -q "OK"; then
    echo -e "${GREEN}  ✓ MAASL lock acquisition works${NC}"
else
    echo -e "${RED}  P1: MAASL lock acquisition failed${NC}"
    ((P1_COUNT++))
    ((ISSUES++))
fi

# --- Check 2: Concurrent database access ---
echo -e "${YELLOW}[2/4] Testing concurrent database access...${NC}"
if python -c "
import sqlite3
import threading
import tempfile
import os

db_path = tempfile.mktemp(suffix='.db')
errors = []

def writer(n):
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        conn.execute('CREATE TABLE IF NOT EXISTS test (id INTEGER)')
        for i in range(10):
            conn.execute(f'INSERT INTO test VALUES ({n * 100 + i})')
        conn.commit()
        conn.close()
    except Exception as e:
        errors.append(str(e))

threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()

os.unlink(db_path)

if errors:
    print(f'ERRORS: {len(errors)}')
else:
    print('OK')
" 2>/dev/null | grep -q "OK"; then
    echo -e "${GREEN}  ✓ Concurrent DB access handled${NC}"
else
    echo -e "${YELLOW}  WARN: Concurrent DB access may have issues${NC}"
fi

# --- Check 3: File locking ---
echo -e "${YELLOW}[3/4] Testing file locking...${NC}"
if python -c "
import fcntl
import tempfile
import os

lock_file = tempfile.mktemp()
with open(lock_file, 'w') as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
os.unlink(lock_file)
print('OK')
" 2>/dev/null | grep -q "OK"; then
    echo -e "${GREEN}  ✓ File locking works${NC}"
else
    echo -e "${RED}  P1: File locking not working${NC}"
    ((P1_COUNT++))
    ((ISSUES++))
fi

# --- Check 4: Deadlock detection (timeout-based) ---
echo -e "${YELLOW}[4/4] Testing deadlock timeout...${NC}"
if timeout 5 python -c "
import threading
import time

# Simple lock that should not deadlock
lock = threading.Lock()
acquired = lock.acquire(timeout=1)
if acquired:
    lock.release()
    print('OK')
else:
    print('TIMEOUT')
" 2>/dev/null | grep -q "OK"; then
    echo -e "${GREEN}  ✓ Lock timeout works${NC}"
else
    echo -e "${RED}  P0: Potential deadlock detected${NC}"
    ((P0_COUNT++))
    ((ISSUES++))
fi

# --- Summary ---
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "  P0 Critical: $P0_COUNT"
echo -e "  P1 High:     $P1_COUNT"
echo -e "  Total:       $ISSUES issues"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

exit $ISSUES
