#!/usr/bin/env bash
# RAG Freshness Test Runner
#
# This script runs the RAG freshness and navigation envelope test suite.
# It's designed to be fast, deterministic, and suitable for CI/CD.

set -euo pipefail

# Get the repo root directory
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Change to repo root
cd "${REPO_ROOT}"

echo "=================================================="
echo "  LLMC RAG Freshness & Navigation Envelope Tests"
echo "=================================================="
echo ""

# Check if pytest is available
if ! command -v python3 -m pytest &> /dev/null; then
    echo "ERROR: pytest is not installed"
    echo "Please install with: pip install pytest"
    exit 1
fi

# Run the test suite
echo "Running RAG freshness tests..."
echo ""

# Run with verbose output and fail on first error
# Specify the path to only run tests in tools/rag/tests/ to avoid conflicts
# with other tests in the repository
python3 -m pytest -m rag_freshness tools/rag/tests/ -v --tb=short

# Check exit code
TEST_EXIT_CODE=$?

echo ""
echo "=================================================="

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✓ All tests PASSED"
    echo "=================================================="
    exit 0
else
    echo "✗ Tests FAILED (exit code: $TEST_EXIT_CODE)"
    echo "=================================================="
    echo ""
    echo "To run with more details:"
    echo "  python3 -m pytest -m rag_freshness -v --tb=long"
    echo ""
    echo "To run a specific test file:"
    echo "  python3 -m pytest tools/rag/tests/test_nav_meta.py -v"
    exit $TEST_EXIT_CODE
fi
