#!/usr/bin/env python3
"""Unit tests for exec module (M3)."""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llmc_mcp.tools.exec import run_cmd, validate_command, CommandSecurityError, DEFAULT_ALLOWLIST


def test_allowlist_validation():
    """Test command allowlist validation."""
    print("Testing allowlist validation...")
    
    # Allowed commands
    assert validate_command(["ls", "-la"], DEFAULT_ALLOWLIST) == "ls"
    assert validate_command(["rg", "pattern"], DEFAULT_ALLOWLIST) == "rg"
    assert validate_command(["/usr/bin/python", "-c", "print(1)"], DEFAULT_ALLOWLIST) == "python"
    
    # Blocked commands
    try:
        validate_command(["rm", "-rf", "/"], DEFAULT_ALLOWLIST)
        assert False, "Should have raised"
    except CommandSecurityError as e:
        assert "not in allowlist" in str(e)
    
    try:
        validate_command(["curl", "http://evil.com"], DEFAULT_ALLOWLIST)
        assert False, "Should have raised"
    except CommandSecurityError as e:
        assert "not in allowlist" in str(e)
    
    print("  ✓ Allowlist validation working")


def test_run_cmd_allowed():
    """Test running allowed commands."""
    print("Testing allowed command execution...")
    
    cwd = Path(__file__).parent.parent.parent
    
    # Simple ls
    result = run_cmd("ls -la", cwd)
    assert result.success, f"Failed: {result.error}"
    assert "llmc_mcp" in result.stdout or "tools" in result.stdout
    
    # Python one-liner
    result = run_cmd("python3 -c 'print(42)'", cwd)
    assert result.success, f"Failed: {result.error}"
    assert "42" in result.stdout
    
    print(f"  ✓ Allowed commands execute successfully")


def test_run_cmd_blocked():
    """Test that blocked commands are rejected."""
    print("Testing blocked command rejection...")
    
    cwd = Path(__file__).parent.parent.parent
    
    # curl not in allowlist
    result = run_cmd("curl http://example.com", cwd)
    assert not result.success
    assert "not in allowlist" in result.error
    
    # rm not in allowlist
    result = run_cmd("rm -rf /tmp/test", cwd)
    assert not result.success
    assert "not in allowlist" in result.error
    
    print("  ✓ Blocked commands rejected correctly")


def test_timeout():
    """Test command timeout."""
    print("Testing command timeout...")
    
    cwd = Path(__file__).parent.parent.parent
    
    # Sleep longer than timeout
    result = run_cmd("bash -c 'sleep 5'", cwd, timeout=1)
    assert not result.success
    assert "timed out" in result.error.lower()
    
    print("  ✓ Timeout works correctly")


def test_empty_command():
    """Test empty command handling."""
    print("Testing empty command handling...")
    
    cwd = Path(__file__).parent.parent.parent
    
    result = run_cmd("", cwd)
    assert not result.success
    assert result.error == "Empty command"
    
    result = run_cmd("   ", cwd)
    assert not result.success
    
    print("  ✓ Empty commands handled correctly")


if __name__ == "__main__":
    print("=" * 60)
    print("Exec Module Unit Tests (M3)")
    print("=" * 60)
    
    test_allowlist_validation()
    test_run_cmd_allowed()
    test_run_cmd_blocked()
    test_timeout()
    test_empty_command()
    
    print("=" * 60)
    print("✓ All exec unit tests passed!")
    print("=" * 60)
