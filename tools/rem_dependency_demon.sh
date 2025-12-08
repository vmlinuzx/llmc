#!/usr/bin/env bash
# ==============================================================================
# DEPENDENCY DEMON - CVE scanning, outdated deps, license issues
# ==============================================================================
#
# Scans dependencies for known vulnerabilities and issues.
#
# Checks:
# - pip-audit for CVEs
# - Outdated packages
# - License compliance (optional)
#
# Usage:
#   ./tools/rem_dependency_demon.sh
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
echo -e "${CYAN}  📦 DEPENDENCY DEMON                                           ${NC}"
echo -e "${CYAN}  CVE scanning and dependency health                            ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

cd "$LLMC_ROOT"
source .venv/bin/activate 2>/dev/null || true

ISSUES=0
P0_COUNT=0
P1_COUNT=0

# --- Check 1: pip-audit for CVEs ---
echo -e "${YELLOW}[1/3] Scanning for known vulnerabilities (pip-audit)...${NC}"
if command -v pip-audit &> /dev/null; then
    AUDIT_OUTPUT=$(pip-audit 2>&1 || true)
    VULN_COUNT=$(echo "$AUDIT_OUTPUT" | grep -c "VULN" || echo "0")
    
    if [[ "$VULN_COUNT" -gt 0 ]]; then
        echo -e "${RED}  P0 CRITICAL: Found $VULN_COUNT known vulnerabilities!${NC}"
        echo "$AUDIT_OUTPUT" | grep "VULN" | head -10
        ((P0_COUNT += VULN_COUNT))
        ((ISSUES += VULN_COUNT))
    else
        echo -e "${GREEN}  ✓ No known vulnerabilities found${NC}"
    fi
else
    echo -e "${YELLOW}  WARN: pip-audit not installed. Run: pip install pip-audit${NC}"
    # Try to install it
    pip install pip-audit -q 2>/dev/null || true
    if command -v pip-audit &> /dev/null; then
        AUDIT_OUTPUT=$(pip-audit 2>&1 || true)
        VULN_COUNT=$(echo "$AUDIT_OUTPUT" | grep -c "VULN" || echo "0")
        if [[ "$VULN_COUNT" -gt 0 ]]; then
            echo -e "${RED}  P0 CRITICAL: Found $VULN_COUNT known vulnerabilities!${NC}"
            ((P0_COUNT += VULN_COUNT))
            ((ISSUES += VULN_COUNT))
        else
            echo -e "${GREEN}  ✓ No known vulnerabilities found${NC}"
        fi
    fi
fi

# --- Check 2: Outdated packages ---
echo -e "${YELLOW}[2/3] Checking for outdated packages...${NC}"
OUTDATED=$(pip list --outdated --format=columns 2>/dev/null | tail -n +3 | wc -l || echo "0")

if [[ "$OUTDATED" -gt 20 ]]; then
    echo -e "${YELLOW}  P1: Many outdated packages: $OUTDATED${NC}"
    pip list --outdated --format=columns 2>/dev/null | head -10
    ((P1_COUNT++))
    ((ISSUES++))
elif [[ "$OUTDATED" -gt 0 ]]; then
    echo -e "${YELLOW}  INFO: $OUTDATED packages have updates available${NC}"
else
    echo -e "${GREEN}  ✓ All packages up to date${NC}"
fi

# --- Check 3: Requirements consistency ---
echo -e "${YELLOW}[3/3] Checking requirements consistency...${NC}"
if [[ -f "pyproject.toml" ]]; then
    # Check if installed packages match pyproject.toml
    MISSING=$(pip check 2>&1 | grep -c "has requirement" || echo "0")
    if [[ "$MISSING" -gt 0 ]]; then
        echo -e "${RED}  P1: Dependency conflicts detected${NC}"
        pip check 2>&1 | head -5
        ((P1_COUNT++))
        ((ISSUES++))
    else
        echo -e "${GREEN}  ✓ Dependencies consistent${NC}"
    fi
else
    echo -e "${YELLOW}  SKIP: No pyproject.toml found${NC}"
fi

# --- Summary ---
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "  P0 Critical (CVEs): $P0_COUNT"
echo -e "  P1 High:            $P1_COUNT"
echo -e "  Total:              $ISSUES issues"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

if [[ $P0_COUNT -gt 0 ]]; then
    echo -e "${RED}⚠️  CRITICAL: Run 'pip-audit --fix' to address vulnerabilities${NC}"
fi

exit $ISSUES
