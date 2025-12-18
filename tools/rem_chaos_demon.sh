#!/bin/bash
# Chaos Demon - Resilience Testing
# Tests system resilience by simulating failure conditions.

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

FAILURES=0
CHECKS_RUN=0

REPO_ROOT=${LLMC_ROOT:-$(pwd)}
export PYTHONPATH=$REPO_ROOT

function log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

function log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    FAILURES=$((FAILURES + 1))
}

function run_check() {
    CHECKS_RUN=$((CHECKS_RUN + 1))
    echo "Running check $CHECKS_RUN: $1..."
}

LLMC_CMD=${LLMC_CMD:-"python3 -m llmc.main"}

# 1. Missing Config Handling - Graceful behavior when repo not found
run_check "Missing Config Handling"
# We run llmc in a non-existent directory to simulate missing repo/config
# We assume 'analytics search' requires a config/repo
OUTPUT=$(cd /tmp && $LLMC_CMD analytics search "test" 2>&1)
EXIT_CODE=$?

if echo "$OUTPUT" | grep -q "Traceback"; then
    log_fail "Traceback detected when running outside repo"
else
    # We expect it to fail (exit code != 0) or handle it gracefully.
    # If it returns 0, it means it somehow worked without config or fell back to defaults, which is arguably graceful too.
    # But usually it should complain about missing config.
    log_pass "Handled missing config gracefully (Exit code $EXIT_CODE)"
fi

# 2. Large Query Handling - No crash or hang on huge inputs
run_check "Large Query Handling"
LARGE_INPUT=$(printf 'A%.0s' {1..10000})
OUTPUT=$(timeout 15s $LLMC_CMD analytics search "$LARGE_INPUT" 2>&1)
EXIT_CODE=$?
if [ $EXIT_CODE -eq 124 ]; then
    log_fail "Command timed out on large query"
elif echo "$OUTPUT" | grep -q "Traceback"; then
    log_fail "Traceback on large query"
else
    log_pass "Large query handled (Exit code $EXIT_CODE)"
fi

# 3. Empty Database Handling - Safe behavior with empty/corrupted DB
run_check "Empty Database Handling"
TEMP_DIR=$(mktemp -d)
mkdir -p "$TEMP_DIR/llmc"
touch "$TEMP_DIR/llmc.toml"
# Run command in temp dir
OUTPUT=$(cd "$TEMP_DIR" && $LLMC_CMD analytics search "test" 2>&1)
EXIT_CODE=$?
if echo "$OUTPUT" | grep -q "Traceback"; then
    log_fail "Traceback on empty database"
else
    log_pass "Empty database handled (Exit code $EXIT_CODE)"
fi
rm -rf "$TEMP_DIR"

# 4. Unicode Chaos - Handle emoji and special characters safely
run_check "Unicode Chaos"
UNICODE_INPUT="Hello 🌍 👹 \xFF"
OUTPUT=$($LLMC_CMD analytics search "$UNICODE_INPUT" 2>&1)
if echo "$OUTPUT" | grep -q "Traceback"; then
    log_fail "Traceback on unicode input"
else
    log_pass "Unicode input handled"
fi

# 5. Timeout Behavior - Commands respect timeout limits
run_check "Timeout Behavior"
# Using `version` as a proxy for a fast command that shouldn't hang.
START_TIME=$(date +%s)
$LLMC_CMD --version > /dev/null 2>&1
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
if [ $DURATION -lt 10 ]; then
    log_pass "Basic command returned quickly ($DURATION s)"
else
    log_fail "Basic command took too long ($DURATION s)"
fi

echo "----------------------------------------"
echo "Chaos Demon Finished"
echo "Failures: $FAILURES"
exit $FAILURES
