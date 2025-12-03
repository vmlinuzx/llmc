#!/usr/bin/env python3
"""Unit tests for cmd module (M3) - blacklist mode."""

from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llmc_mcp.tools.cmd import DEFAULT_BLACKLIST, CommandSecurityError, run_cmd, validate_command


def test_blacklist_validation():
    """Test command blacklist validation."""
    print("Testing blacklist validation...")

    # With empty blacklist, everything should be allowed
    assert validate_command(["ls", "-la"], DEFAULT_BLACKLIST) == "ls"
    assert validate_command(["rg", "pattern"], DEFAULT_BLACKLIST) == "rg"
    assert validate_command(["/usr/bin/python", "-c", "print(1)"], DEFAULT_BLACKLIST) == "python"
    assert validate_command(["curl", "http://example.com"], DEFAULT_BLACKLIST) == "curl"
    assert validate_command(["sed", "-i", "s/foo/bar/"], DEFAULT_BLACKLIST) == "sed"
    
    # With explicit blacklist, blocked commands should raise
    test_blacklist = ["rm", "chmod", "chown"]
    
    try:
        validate_command(["rm", "-rf", "/"], test_blacklist)
        raise AssertionError("Should have raised for rm")
    except CommandSecurityError as e:
        assert "blacklisted" in str(e)

    try:
        validate_command(["chmod", "777", "file"], test_blacklist)
        raise AssertionError("Should have raised for chmod")
    except CommandSecurityError as e:
        assert "blacklisted" in str(e)
    
    # Non-blacklisted commands should still work
    assert validate_command(["ls", "-la"], test_blacklist) == "ls"
    assert validate_command(["curl", "http://example.com"], test_blacklist) == "curl"

    print("  ✓ Blacklist validation working")


def test_run_cmd_allowed():
    """Test running commands (all allowed with empty blacklist)."""
    print("Testing command execution...")

    cwd = Path(__file__).parent.parent.parent

    # Simple ls
    result = run_cmd("ls -la", cwd)
    assert result.success, f"Failed: {result.error}"
    assert "llmc_mcp" in result.stdout or "tools" in result.stdout

    # Python one-liner
    result = run_cmd("python3 -c 'print(42)'", cwd)
    assert result.success, f"Failed: {result.error}"
    assert "42" in result.stdout
    
    # sed should work now (was blocked by allowlist before)
    result = run_cmd("echo 'hello' | sed 's/hello/world/'", cwd)
    # Note: This runs through bash, so it should work
    assert result.success or "sed" not in result.error, f"Unexpected error: {result.error}"

    print("  ✓ Commands execute successfully")


def test_run_cmd_with_blacklist():
    """Test that blacklisted commands are rejected."""
    print("Testing blacklist enforcement...")

    cwd = Path(__file__).parent.parent.parent
    test_blacklist = ["curl", "wget"]

    # curl is blacklisted
    result = run_cmd("curl http://example.com", cwd, blacklist=test_blacklist)
    assert not result.success
    assert "blacklisted" in result.error

    # wget is blacklisted
    result = run_cmd("wget http://example.com", cwd, blacklist=test_blacklist)
    assert not result.success
    assert "blacklisted" in result.error
    
    # ls is not blacklisted
    result = run_cmd("ls -la", cwd, blacklist=test_blacklist)
    assert result.success, f"ls should work: {result.error}"

    print("  ✓ Blacklist enforcement working")


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
    print("Cmd Module Unit Tests (M3) - Blacklist Mode")
    print("=" * 60)

    test_blacklist_validation()
    test_run_cmd_allowed()
    test_run_cmd_with_blacklist()
    test_timeout()
    test_empty_command()

    print("=" * 60)
    print("✓ All cmd unit tests passed!")
    print("=" * 60)
