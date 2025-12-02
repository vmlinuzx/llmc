#!/usr/bin/env python3
"""
Test suite for Bug Sweep December 2025 - High Priority Fixes

Tests for:
1. H-1: Query timeout prevention (very long queries)
2. H-2: Search command input validation (negative limits)
"""
from pathlib import Path
import subprocess
import sys

repo_root = Path(__file__).resolve().parents[1]


def test_search_negative_limit():
    """Test that search command rejects negative limits."""
    print("Test 1: Search with negative limit should fail gracefully...")
    
    result = subprocess.run(
        [sys.executable, "-m", "llmc", "search", "--limit", "-999", "test"],
        check=False, cwd=repo_root,
        capture_output=True,
        text=True,
    )
    
    assert result.returncode == 1, f"Expected exit code 1, got {result.returncode}"
    assert "must be a positive integer" in result.stderr, f"Expected validation error, got: {result.stderr}"
    print("  ✅ PASS - Negative limit properly rejected")


def test_search_zero_limit():
    """Test that search command rejects zero limit."""
    print("Test 2: Search with zero limit should fail gracefully...")
    
    result = subprocess.run(
        [sys.executable, "-m", "llmc", "search", "--limit", "0", "test"],
        check=False, cwd=repo_root,
        capture_output=True,
        text=True,
    )
    
    assert result.returncode == 1, f"Expected exit code 1, got {result.returncode}"
    assert "must be a positive integer" in result.stderr, f"Expected validation error, got: {result.stderr}"
    print("  ✅ PASS - Zero limit properly rejected")


def test_search_very_long_query():
    """Test that search command rejects excessively long queries."""
    print("Test 3: Search with very long query should fail with timeout prevention...")
    
    long_query = "x" * 10000  # 10,000 character query
    result = subprocess.run(
        [sys.executable, "-m", "llmc", "search", "--limit", "10", long_query],
        check=False, cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10,  # Should fail quickly, not timeout
    )
    
    assert result.returncode == 1, f"Expected exit code 1, got {result.returncode}"
    assert "Query too long" in result.stderr, f"Expected length error, got: {result.stderr}"
    assert "10000 chars" in result.stderr, "Expected to show actual length"
    assert "Maximum allowed: 5000 chars" in result.stderr, "Expected to show limit"
    print("  ✅ PASS - Very long query properly rejected (prevents timeout)")


def test_search_boundary_query_length():
    """Test that search accepts queries at the maximum length."""
    print("Test 4: Search with query at max length (5000 chars) should succeed...")
    
    max_length_query = "x" * 5000  # Exactly at limit
    result = subprocess.run(
        [sys.executable, "-m", "llmc", "search", "--limit", "10", max_length_query],
        check=False, cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,  # Reasonable timeout for valid query
    )
    
    # Should not fail with validation error (might fail with "no results" which is OK)
    if result.returncode != 0:
        # Check it's not a validation error
        assert "Query too long" not in result.stderr, "Should accept 5000 char query"
        assert "must be a positive integer" not in result.stderr, "Should accept valid limit"
    
    print("  ✅ PASS - Query at maximum length accepted")


def test_search_slightly_over_limit():
    """Test that search rejects queries just over the limit."""
    print("Test 5: Search with query slightly over limit (5001 chars) should fail...")
    
    over_limit_query = "x" * 5001  # Just over limit
    result = subprocess.run(
        [sys.executable, "-m", "llmc", "search", "--limit", "10", over_limit_query],
        check=False, cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10,
    )
    
    assert result.returncode == 1, f"Expected exit code 1, got {result.returncode}"
    assert "Query too long" in result.stderr, "Expected length error"
    assert "5001 chars" in result.stderr, "Expected to show actual length"
    print("  ✅ PASS - Query over limit properly rejected")


def main():
    print("\n" + "=" * 70)
    print("BUG SWEEP DEC 2025 - HIGH PRIORITY FIXES TEST SUITE")
    print("=" * 70)
    print()
    print("Testing fixes for:")
    print("  H-1: Very long query timeout (performance)")
    print("  H-2: Search command input validation (negative limits)")
    print()
    print("-" * 70)
    print()
    
    tests = [
        test_search_negative_limit,
        test_search_zero_limit,
        test_search_very_long_query,
        test_search_boundary_query_length,
        test_search_slightly_over_limit,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAIL - {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ ERROR - {e}")
            failed += 1
        print()
    
    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed > 0:
        return 1
    
    print()
    print("✅ All high-priority bug fixes verified!")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
