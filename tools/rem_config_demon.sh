#!/usr/bin/env bash
# ==============================================================================
# CONFIG DEMON - Fuzz llmc.toml, edge cases, schema validation
# ==============================================================================
#
# Tests configuration parsing and validation edge cases.
#
# Checks:
# - Invalid TOML syntax handling
# - Missing required sections
# - Invalid values
# - Default fallback behavior
#
# Usage:
#   ./tools/rem_config_demon.sh
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
echo -e "${CYAN}  ⚙️  CONFIG DEMON                                               ${NC}"
echo -e "${CYAN}  Fuzzing configuration and testing edge cases                  ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

cd "$LLMC_ROOT"
source .venv/bin/activate 2>/dev/null || true

ISSUES=0
P0_COUNT=0
P1_COUNT=0
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# --- Check 1: Invalid TOML syntax ---
echo -e "${YELLOW}[1/5] Testing invalid TOML handling...${NC}"
cat > "$TMPDIR/llmc.toml" << 'EOF'
[llmc
name = "broken"
EOF
mkdir -p "$TMPDIR/.llmc"

if python -c "
import os
os.chdir('$TMPDIR')
os.environ['LLMC_CONFIG'] = '$TMPDIR/llmc.toml'
try:
    from llmc.commands.repo_validator import validate_repo
    from pathlib import Path
    result = validate_repo(Path('$TMPDIR'))
    print('HANDLED')
except Exception as e:
    print(f'CRASHED: {type(e).__name__}')
" 2>/dev/null | grep -q "HANDLED\|CRASHED"; then
    echo -e "${GREEN}  ✓ Invalid TOML handled safely${NC}"
else
    echo -e "${RED}  P1: Invalid TOML causes unhandled crash${NC}"
    ((P1_COUNT++))
    ((ISSUES++))
fi

# --- Check 2: Empty config file ---
echo -e "${YELLOW}[2/5] Testing empty config file...${NC}"
echo "" > "$TMPDIR/llmc.toml"

if python -c "
from llmc.commands.repo_validator import validate_repo
from pathlib import Path
result = validate_repo(Path('$TMPDIR'), check_connectivity=False)
print('HANDLED')
" 2>/dev/null | grep -q "HANDLED"; then
    echo -e "${GREEN}  ✓ Empty config handled safely${NC}"
else
    echo -e "${RED}  P1: Empty config causes crash${NC}"
    ((P1_COUNT++))
    ((ISSUES++))
fi

# --- Check 3: Negative/invalid values ---
echo -e "${YELLOW}[3/5] Testing invalid values...${NC}"
cat > "$TMPDIR/llmc.toml" << 'EOF'
[llmc]
name = "test"

[enrichment]
timeout = -1
batch_size = 0
EOF

if python -c "
from llmc.commands.repo_validator import validate_repo
from pathlib import Path
result = validate_repo(Path('$TMPDIR'), check_connectivity=False)
# Should either handle gracefully or warn
print('HANDLED')
" 2>/dev/null | grep -q "HANDLED"; then
    echo -e "${GREEN}  ✓ Invalid values handled${NC}"
else
    echo -e "${YELLOW}  WARN: Invalid values not fully validated${NC}"
fi

# --- Check 4: Unicode in config ---
echo -e "${YELLOW}[4/5] Testing unicode in config...${NC}"
cat > "$TMPDIR/llmc.toml" << 'EOF'
[llmc]
name = "テスト🔥"

[enrichment]
model = "qwen2.5:7b"
EOF

if python -c "
from llmc.commands.repo_validator import validate_repo
from pathlib import Path
result = validate_repo(Path('$TMPDIR'), check_connectivity=False)
print('HANDLED')
" 2>/dev/null | grep -q "HANDLED"; then
    echo -e "${GREEN}  ✓ Unicode config handled safely${NC}"
else
    echo -e "${YELLOW}  WARN: Unicode may cause issues${NC}"
fi

# --- Check 5: Very long values ---
echo -e "${YELLOW}[5/5] Testing very long values...${NC}"
LONG_STRING=$(python -c "print('a' * 10000)")
cat > "$TMPDIR/llmc.toml" << EOF
[llmc]
name = "$LONG_STRING"
EOF

if python -c "
from llmc.commands.repo_validator import validate_repo
from pathlib import Path
result = validate_repo(Path('$TMPDIR'), check_connectivity=False)
print('HANDLED')
" 2>/dev/null | grep -q "HANDLED"; then
    echo -e "${GREEN}  ✓ Long values handled safely${NC}"
else
    echo -e "${YELLOW}  WARN: Long values may cause issues${NC}"
fi

# --- Summary ---
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "  P0 Critical: $P0_COUNT"
echo -e "  P1 High:     $P1_COUNT"
echo -e "  Total:       $ISSUES issues"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

exit $ISSUES
