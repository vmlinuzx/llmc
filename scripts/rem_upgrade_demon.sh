#!/bin/bash
# Upgrade Demon - Version Migration Testing
# Validates version migration safety by checking DB migrations, config validity,
# deprecated API usage, and index readability.

# Purpose: Tests upgrade paths and migration safety.

set -e

# Default to current directory if LLMC_ROOT not set
LLMC_ROOT="${LLMC_ROOT:-$(pwd)}"

# Ensure we are in the root (basic check)
if [ ! -f "$LLMC_ROOT/llmc.toml" ] && [ ! -f "$LLMC_ROOT/pyproject.toml" ]; then
    # Try one level up if we are in tools/ or scripts/
    if [ -f "$LLMC_ROOT/../llmc.toml" ]; then
        LLMC_ROOT="$LLMC_ROOT/.."
    else
        echo "Error: LLMC_ROOT ($LLMC_ROOT) does not appear to be the repository root."
        exit 1
    fi
fi

cd "$LLMC_ROOT"

echo "================================================================"
echo "😈 UPGRADE DEMON: Checking Migration Safety"
echo "================================================================"

FAILURES=0

# 1. DB Migration Check
echo -n "1. DB Migration Check... "
DB_PATH=""
# Try to find the DB
if [ -f ".llmc/rag/index.db" ]; then
    DB_PATH=".llmc/rag/index.db"
elif [ -f ".rag/index_v2.db" ]; then
    DB_PATH=".rag/index_v2.db"
elif [ -f "metrics/rag-service.db" ]; then
    DB_PATH="metrics/rag-service.db"
fi

if [ -n "$DB_PATH" ] && [ -f "$DB_PATH" ]; then
    # Check if DB is readable
    if sqlite3 "$DB_PATH" "PRAGMA table_info(enrichments);" > /dev/null 2>&1; then
        # Run migration scripts safely
        if [ -f "scripts/migrate_add_enrichment_metrics.py" ]; then
            if python3 scripts/migrate_add_enrichment_metrics.py "$LLMC_ROOT" > /dev/null 2>&1; then
                 echo "PASS (DB Readable & Migrations OK)"
            else
                 echo "FAIL (Migration Script Failed)"
                 FAILURES=$((FAILURES + 1))
            fi
        else
            echo "PASS (DB Readable, Migration script missing)"
        fi
    else
        echo "FAIL (DB Corrupt or Locked)"
        FAILURES=$((FAILURES + 1))
    fi
else
    echo "SKIP (No DB found)"
fi

# 2. Config Migration Check
echo -n "2. Config Migration Check... "
CONFIG_PATH="llmc.toml"
if [ -f "$CONFIG_PATH" ]; then
    # Validate TOML syntax using python (tomllib is stdlib in 3.11+, fallback to tomli)
    CHECK_CMD="
import sys
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print('MISSING_DEP')
        sys.exit(1)
try:
    with open('$CONFIG_PATH', 'rb') as f:
        tomllib.load(f)
except Exception:
    sys.exit(1)
"

    # Run python check and capture output/status
    CHECK_OUTPUT=$(python3 -c "$CHECK_CMD" 2>&1 || echo "FAILED")

    if [ "$CHECK_OUTPUT" != "FAILED" ] && [ "$CHECK_OUTPUT" != "MISSING_DEP" ]; then
         echo "PASS (Valid TOML)"
    elif [[ "$CHECK_OUTPUT" == *"MISSING_DEP"* ]]; then
         echo "WARN (Skipping config check: python 3.11+ or tomli required)"
    else
         echo "FAIL (Invalid TOML)"
         FAILURES=$((FAILURES + 1))
    fi
else
    echo "FAIL (Config missing)"
    FAILURES=$((FAILURES + 1))
fi

# 3. Breaking Changes Check
echo -n "3. Breaking Changes Check... "
# Scan for explicitly marked deprecated items in Python code
DEPRECATED_COUNT=$(grep -r --include="*.py" "DEPRECATED" llmc/ 2>/dev/null | wc -l)
if [ "$DEPRECATED_COUNT" -gt 0 ]; then
    echo "WARN ($DEPRECATED_COUNT deprecated items found)"
else
    echo "PASS (No explicit deprecations found)"
fi

# 4. Backwards Compatibility
echo -n "4. Backwards Compatibility... "
if [ -n "$DB_PATH" ] && [ -f "$DB_PATH" ]; then
    # Check if we can read enrichments
    if sqlite3 "$DB_PATH" "SELECT count(*) FROM enrichments;" >/dev/null 2>&1; then
         echo "PASS (Old data readable)"
    else
         echo "WARN (Cannot read enrichments table - maybe empty DB)"
    fi
else
    echo "SKIP (No DB)"
fi

# 5. Rollback Safety
echo -n "5. Rollback Safety... "
if [ -n "$DB_PATH" ] && [ -f "$DB_PATH" ]; then
    BACKUP_PATH="${DB_PATH}.bak_upgrade_demon"
    if cp "$DB_PATH" "$BACKUP_PATH"; then
        echo "PASS (Backup created)"
        rm "$BACKUP_PATH"
    else
        echo "FAIL (Backup failed)"
        FAILURES=$((FAILURES + 1))
    fi
else
    echo "SKIP (No DB)"
fi

echo "================================================================"
if [ "$FAILURES" -eq 0 ]; then
    echo "✅ UPGRADE DEMON: All Checks Passed"
    exit 0
else
    echo "❌ UPGRADE DEMON: $FAILURES Checks Failed"
    exit 1
fi
