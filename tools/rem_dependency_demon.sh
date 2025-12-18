#!/bin/bash

# Dependency Demon - CVE & Outdated Package Scanner

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

REPO_ROOT="${LLMC_ROOT:-$(pwd)}"
cd "$REPO_ROOT" || {
    echo -e "${RED}Error: Cannot change to $REPO_ROOT${NC}"
    exit 1
}

# 1. Dependency Check
if ! command -v pip-audit &> /dev/null; then
    echo -e "${RED}Error: pip-audit not found.${NC}"
    echo "Please install it: pip install pip-audit"
    exit 1
fi

echo -e "\n${BLUE}=== 1. Checking for CVEs (pip-audit) ===${NC}"
TMP_JSON=$(mktemp)
# Run pip-audit, capture JSON.
pip-audit -f json > "$TMP_JSON" 2>/dev/null
AUDIT_STATUS=$?

CRITICAL_COUNT=0

if [ $AUDIT_STATUS -eq 0 ]; then
    echo -e "${GREEN}No known vulnerabilities found.${NC}"
else
    # Parse JSON
    python3 -c "
import sys, json

try:
    with open('$TMP_JSON') as f:
        data = json.load(f)
except Exception as e:
    print(f'Error parsing pip-audit output: {e}')
    # If parsing fails but pip-audit failed, assume critical failure
    with open('$TMP_JSON.count', 'w') as f:
        f.write('1')
    sys.exit(0)

critical_count = 0
dependencies = data.get('dependencies', [])
found_vulns = False

for dep in dependencies:
    vulns = dep.get('vulns', [])
    if not vulns:
        continue

    found_vulns = True
    print(f'\n{dep.get("name")} ({dep.get("version")}):')

    for vuln in vulns:
        vid = vuln.get('id')
        aliases = vuln.get('aliases', [])

        # FAIL CLOSED: Treat all detected vulnerabilities as potentially Critical.
        # TODO: Future improvement: Parse CycloneDX format (pip-audit -f cyclonedx-json)
        # to extract actual CVSS scores and implement P0-P3 mapping.

        label = 'UNKNOWN - Assumed Critical'
        color = '${RED}'
        critical_count += 1

        print(f'  - {color}[{label}] {vid}{NC} {aliases}')

if not found_vulns:
    print('No vulnerabilities found (but pip-audit returned error?).')

with open('$TMP_JSON.count', 'w') as f:
    f.write(str(critical_count))
"

    if [ -f "$TMP_JSON.count" ]; then
        CRITICAL_COUNT=$(cat "$TMP_JSON.count")
        rm "$TMP_JSON.count"
    fi
    rm "$TMP_JSON"
fi

echo -e "\n${BLUE}=== 2. Checking Outdated Packages ===${NC}"
pip list --outdated

echo -e "\n${BLUE}=== 3. Requirements Drift ===${NC}"
if [ -f "requirements.txt" ]; then
    echo "Checking against requirements.txt..."
    MISSING_COUNT=0
    # Naive parsing of requirements.txt
    while read -r line; do
        # Ignore comments
        [[ "$line" =~ ^#.*$ ]] && continue
        # Ignore empty lines
        [[ -z "$line" ]] && continue
        # Ignore flags/options (lines starting with -)
        [[ "$line" =~ ^-.*$ ]] && continue

        PKG_NAME=$(echo "$line" | sed -E 's/([^<>=!\[]+).*/\1/')
        PKG_NAME=$(echo "$PKG_NAME" | xargs)
        if [ -n "$PKG_NAME" ]; then
            if ! pip show "$PKG_NAME" &> /dev/null; then
                echo -e "${RED}Missing: $PKG_NAME${NC}"
                MISSING_COUNT=$((MISSING_COUNT + 1))
            fi
        fi
    done < requirements.txt

    if [ $MISSING_COUNT -eq 0 ]; then
        echo -e "${GREEN}All required packages installed.${NC}"
    else
        echo -e "${RED}Found $MISSING_COUNT missing packages.${NC}"
    fi
else
    echo "No requirements.txt found. Skipping drift check."
fi

echo -e "\n${BLUE}=== Scan Complete ===${NC}"
echo "Critical Vulnerabilities: $CRITICAL_COUNT"

exit $CRITICAL_COUNT
