#!/usr/bin/env bash
# ==============================================================================
# DOCUMENTATION DEMON - Stale docs, broken links, missing docstrings
# ==============================================================================
#
# Hunts for documentation rot and inconsistencies.
#
# Checks:
# - Broken internal links in markdown
# - Referenced commands that don't exist
# - Missing docstrings in public functions
# - Outdated version numbers
#
# Usage:
#   ./tools/rem_documentation_demon.sh
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
echo -e "${CYAN}  📚 DOCUMENTATION DEMON                                        ${NC}"
echo -e "${CYAN}  Hunting stale docs and broken links                           ${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

cd "$LLMC_ROOT"

ISSUES=0
P0_COUNT=0
P1_COUNT=0

# --- Check 1: Broken internal links ---
echo -e "${YELLOW}[1/4] Checking for broken internal links...${NC}"
BROKEN_LINKS=0
while IFS= read -r md_file; do
    # Extract markdown links and check if targets exist
    while IFS= read -r link; do
        if [[ -n "$link" && ! "$link" =~ ^http && ! "$link" =~ ^# ]]; then
            # Get directory of current file for relative resolution
            dir=$(dirname "$md_file")
            target="$dir/$link"
            # Remove anchor
            target="${target%%#*}"
            if [[ ! -e "$target" && ! -e "$LLMC_ROOT/$link" ]]; then
                echo -e "${RED}  Broken: $md_file -> $link${NC}"
                ((BROKEN_LINKS++))
            fi
        fi
    done < <(grep -oP '\[.*?\]\(\K[^)]+' "$md_file" 2>/dev/null || true)
done < <(find DOCS -name "*.md" -type f 2>/dev/null)

if [[ "$BROKEN_LINKS" -gt 0 ]]; then
    echo -e "${RED}  P1: Found $BROKEN_LINKS broken links${NC}"
    ((P1_COUNT++))
    ((ISSUES++))
else
    echo -e "${GREEN}  ✓ No broken internal links${NC}"
fi

# --- Check 2: Ghost CLI commands ---
echo -e "${YELLOW}[2/4] Checking for documented but non-existent commands...${NC}"
GHOST_CMDS=0

# Look for 'llmc docs generate' which is known to not exist
if grep -r "llmc docs generate" DOCS/ 2>/dev/null | grep -v "doesn't exist" | grep -v "#" | head -1 | grep -q .; then
    echo -e "${RED}  P1: 'llmc docs generate' documented but doesn't exist${NC}"
    ((GHOST_CMDS++))
fi

if [[ "$GHOST_CMDS" -gt 0 ]]; then
    ((P1_COUNT++))
    ((ISSUES++))
else
    echo -e "${GREEN}  ✓ No ghost commands found${NC}"
fi

# --- Check 3: Missing docstrings ---
echo -e "${YELLOW}[3/4] Checking for missing docstrings in public modules...${NC}"
MISSING_DOCS=$(python -c "
import ast
import sys
from pathlib import Path

missing = 0
for py_file in Path('llmc').glob('**/*.py'):
    if '__pycache__' in str(py_file):
        continue
    try:
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                if not node.name.startswith('_'):
                    if not ast.get_docstring(node):
                        missing += 1
    except:
        pass
print(missing)
" 2>/dev/null || echo "0")

if [[ "$MISSING_DOCS" -gt 50 ]]; then
    echo -e "${YELLOW}  INFO: $MISSING_DOCS public items missing docstrings${NC}"
else
    echo -e "${GREEN}  ✓ Docstring coverage acceptable${NC}"
fi

# --- Check 4: Version consistency ---
echo -e "${YELLOW}[4/4] Checking version consistency...${NC}"
PYPROJECT_VER=$(grep -oP 'version = "\K[^"]+' pyproject.toml 2>/dev/null || echo "unknown")
README_VER=$(grep -oP 'v[0-9]+\.[0-9]+\.[0-9]+' README.md 2>/dev/null | head -1 || echo "unknown")
CHANGELOG_VER=$(grep -oP '^\## \[\K[0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md 2>/dev/null | head -1 || echo "unknown")

echo "  pyproject.toml: $PYPROJECT_VER"
echo "  README.md: $README_VER"
echo "  CHANGELOG.md: $CHANGELOG_VER"

if [[ "$PYPROJECT_VER" != "unknown" && "$CHANGELOG_VER" != "unknown" ]]; then
    if [[ "v$PYPROJECT_VER" != "$README_VER" && "v$CHANGELOG_VER" != "$README_VER" ]]; then
        echo -e "${YELLOW}  WARN: Version mismatch detected${NC}"
    else
        echo -e "${GREEN}  ✓ Versions look consistent${NC}"
    fi
fi

# --- Summary ---
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "  P0 Critical: $P0_COUNT"
echo -e "  P1 High:     $P1_COUNT"
echo -e "  Total:       $ISSUES issues"
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"

exit $ISSUES
