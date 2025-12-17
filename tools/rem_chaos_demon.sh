#!/bin/bash

# Chaos Demon - Resilience Testing
# Tests system resilience by simulating failure conditions.

# Determine command
if command -v llmc &> /dev/null; then
    CMD="llmc"
else
    CMD="python3 -m llmc.main"
fi

P0_COUNT=0
P1_COUNT=0
ISSUES=0

# Cleanup trap
cleanup() {
    rm -f /tmp/large_input.txt /tmp/out.txt /tmp/chaos_demon_*.txt
    rm -rf /tmp/empty_llmc_repo
}
trap cleanup EXIT

# Helper function for reporting
report() {
    local check_name="$1"
    local status="$2"
    local severity="$3" # P0 or P1

    if [ "$status" -eq 0 ]; then
        echo "[PASS] $check_name"
    else
        echo "[FAIL] $check_name"
        if [ "$severity" == "P0" ]; then
            P0_COUNT=$((P0_COUNT + 1))
        else
            P1_COUNT=$((P1_COUNT + 1))
        fi
        ISSUES=$((ISSUES + 1))
    fi
}

echo "Starting Chaos Demon - Resilience Testing..."
echo "Using command: $CMD"

# 1. Missing Config Handling - Graceful behavior when repo not found
echo "--- Check 1: Missing Config Handling ---"
# Run with invalid LLMC_ROOT
OUTPUT=$(LLMC_ROOT=/tmp/nonexistent_chaos_demon $CMD repo status 2>&1)
RET=$?
# We expect non-zero exit code (because repo doesn't exist) BUT no python traceback
if echo "$OUTPUT" | grep -q "Traceback"; then
    echo "Output contained Traceback"
    report "Missing Config Handling" 1 "P0"
else
    # Non-zero exit is fine, as long as no traceback
    report "Missing Config Handling" 0 "P0"
fi

# 2. Large Query Handling - No crash or hang on huge inputs
echo "--- Check 2: Large Query Handling ---"
# Create a large string (50KB)
LARGE_INPUT=$(printf 'A%.0s' {1..50000})
echo "$LARGE_INPUT" > /tmp/large_input.txt

# Run command with large input. We expect it not to crash (segfault)
# We accept exit code 0 or 1, just not 139 (SIGSEGV) or Traceback.
# Note: This depends on ARG_MAX. 50KB should be safe on modern Linux.
$CMD chat "$(cat /tmp/large_input.txt)" > /tmp/out.txt 2>&1
RET=$?
OUTPUT=$(cat /tmp/out.txt)

if [ $RET -eq 139 ]; then
    echo "Segfault detected"
    report "Large Query Handling" 1 "P0"
elif echo "$OUTPUT" | grep -q "Traceback"; then
    echo "Traceback detected"
    report "Large Query Handling" 1 "P0"
else
    report "Large Query Handling" 0 "P1"
fi

# 3. Empty Database Handling - Safe behavior with empty/corrupted DB
echo "--- Check 3: Empty Database Handling ---"
# Create empty dir
mkdir -p /tmp/empty_llmc_repo
# Run a command that usually accesses DB
OUTPUT=$(LLMC_ROOT=/tmp/empty_llmc_repo $CMD repo status 2>&1)
RET=$?
if echo "$OUTPUT" | grep -q "Traceback"; then
    report "Empty Database Handling" 1 "P0"
else
    report "Empty Database Handling" 0 "P1"
fi

# 4. Unicode Chaos - Handle emoji and special characters safely
echo "--- Check 4: Unicode Chaos ---"
UNICODE_INPUT="Testing 🚀🔥👨‍💻 and some \x00 null bytes and other junk: ¥€$£¢"
OUTPUT=$($CMD chat "$UNICODE_INPUT" 2>&1)
RET=$?
if echo "$OUTPUT" | grep -q "Traceback"; then
    report "Unicode Chaos" 1 "P0"
elif [ $RET -eq 139 ]; then
    report "Unicode Chaos" 1 "P0"
else
    report "Unicode Chaos" 0 "P1"
fi

# 5. Timeout Behavior - Commands respect timeout limits
echo "--- Check 5: Timeout Behavior ---"
# We wrap execution in 'timeout' to ensure it doesn't hang indefinitely.
# We set a short timeout (10s) for a simple command like --version or help.
timeout 10s $CMD --version > /dev/null 2>&1
RET=$?
if [ $RET -eq 124 ]; then
    # Timed out
    echo "Command timed out (system timeout)"
    report "Timeout Behavior (Responsiveness)" 1 "P1"
else
    report "Timeout Behavior (Responsiveness)" 0 "P1"
fi

# Summary
echo "---------------------------------------------------"
echo "Chaos Demon Results:"
echo "P0 Issues: $P0_COUNT"
echo "P1 Issues: $P1_COUNT"
echo "Total Issues: $ISSUES"

exit $ISSUES
