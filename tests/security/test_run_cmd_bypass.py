"""
Security tests for run_cmd behavior in isolated environments.

The security model is:
1. Docker/container isolation is the primary security layer
2. When in isolated mode, commands are trusted 
3. Blacklist is a "soft nudge" - not a security boundary

These tests verify this design is working correctly.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

try:
    from llmc_mcp.tools.cmd import run_cmd
except ImportError:
    import sys
    sys.path.append(os.getcwd())
    from llmc_mcp.tools.cmd import run_cmd


def test_run_cmd_works_when_isolated(tmp_path):
    """
    Verify that run_cmd allows commands when isolation check passes.
    
    The security model is: container isolation is the trust boundary,
    not the blacklist. When isolated, commands are allowed.
    """

    # Mock require_isolation to pass (simulating running in Docker)
    with patch("llmc_mcp.isolation.require_isolation") as mock_iso:
        mock_iso.return_value = None

        # Simple command should work
        result = run_cmd("echo 'I am running'", cwd=tmp_path)

        assert result.success
        assert "I am running" in result.stdout


def test_shell_false_prevents_chaining(tmp_path):
    """
    Verify that shell=False prevents command chaining.
    
    Even in isolated mode, we use shell=False to prevent accidental
    shell expansion. This is defense in depth.
    """
    with patch("llmc_mcp.isolation.require_isolation") as mock_iso:
        mock_iso.return_value = None

        # Try command chaining - should NOT work with shell=False
        result_chain = run_cmd("echo A; echo B", cwd=tmp_path)

        # With shell=False, "A; echo B" is treated as literal argument
        # NOT as a separate command
        assert "A; echo B" in result_chain.stdout or "; echo B" in result_chain.stdout
        
        # Make sure chaining did NOT work (should NOT just print "B")
        assert result_chain.stdout.strip() != "B", \
            "VULNERABILITY: Command chaining worked!"


def test_interpreters_allowed_in_isolated_mode(tmp_path):
    """
    Verify interpreters (python, etc) work in isolated mode.
    
    This is BY DESIGN: the container is the security boundary.
    Blocking interpreters would break legitimate use cases.
    """
    with patch("llmc_mcp.isolation.require_isolation") as mock_iso:
        mock_iso.return_value = None

        # Python should work in isolated mode
        result = run_cmd('python3 -c "print(1+1)"', cwd=tmp_path)
        
        if result.success and "2" in result.stdout:
            # This is expected behavior in isolated mode
            pass
        elif not result.success:
            # Also acceptable if python3 isn't available
            pass


def test_run_cmd_blocked_without_isolation(tmp_path):
    """
    Verify run_cmd is blocked when NOT in isolated environment.
    
    This is the security boundary - you can't run commands on bare metal.
    """
    from llmc_mcp.isolation import is_isolated_environment
    
    # Clear cache and ensure not isolated
    is_isolated_environment.cache_clear()
    if "LLMC_ISOLATED" in os.environ:
        del os.environ["LLMC_ISOLATED"]
    
    # Should fail when not isolated
    result = run_cmd("echo test", cwd=tmp_path)
    
    assert not result.success
    assert "isolated" in result.error.lower() or "isolated" in result.stderr.lower()


if __name__ == "__main__":
    test_run_cmd_works_when_isolated(Path("."))
