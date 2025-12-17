import pytest

from llmc_mcp.tools.cmd import CommandSecurityError, validate_command


def test_direct_block():
    """Verify that a blacklisted command is directly blocked."""
    with pytest.raises(CommandSecurityError):
        validate_command(["node", "script.js"], blacklist=["node"])


def test_path_resolution():
    """Verify that a blacklisted command is blocked even when referenced by absolute path."""
    with pytest.raises(CommandSecurityError):
        validate_command(["/usr/bin/node", "script.js"], blacklist=["node"])


def test_argument_bypass():
    """
    Verify the gap: a blacklisted command can be executed if passed as an argument
    to a non-blacklisted command (e.g., bash).
    """
    # This should NOT raise CommandSecurityError because 'bash' is not blacklisted
    # and the validation logic only checks the first token (the binary).
    # If this raises, the security gap has been closed (or the test is wrong).
    result = validate_command(["bash", "-c", "node script.js"], blacklist=["node"])
    assert result == "bash"
