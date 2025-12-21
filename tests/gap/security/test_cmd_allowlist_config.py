from unittest.mock import patch
import pytest
from llmc_mcp.config import load_config
from llmc_mcp.tools.cmd import run_cmd


@pytest.mark.skip(reason="Known security gap - allowlist is not yet implemented")
def test_cmd_allowlist_config_mismatch(tmp_path):
    """
    Test that the 'run_cmd_allowlist' in llmc.toml is currently ignored,
    leading to a security fail-open state where commands not in the allowlist are executed.

    See: tests/gap/SDDs/SDD-Security-CmdAllowlist.md
    """

    # 1. Create a temporary llmc.toml with an explicit allowlist
    config_content = """
[mcp.tools]
enable_run_cmd = true
run_cmd_allowlist = ["ls", "echo"]
"""
    config_file = tmp_path / "llmc.toml"
    config_file.write_text(config_content, encoding="utf-8")

    # 2. Load the configuration
    config = load_config(config_file)

    # 3. Assertions on the Config Object
    # The bug is that 'run_cmd_allowlist' is ignored, and 'run_cmd_blacklist' defaults to empty.
    assert (
        config.tools.run_cmd_blacklist == []
    ), "Blacklist should be empty as it wasn't specified"

    # Check that the config object doesn't even have the allowlist field (confirming the gap)
    assert not hasattr(
        config.tools, "run_cmd_allowlist"
    ), "Config model is missing 'run_cmd_allowlist'"

    # 4. Execution Test
    # We try to run a command that is NOT in the allowlist (e.g., 'whoami').
    # Desired behavior: It should be blocked.
    # Current behavior (Bug): It runs because the blacklist is empty and allowlist is ignored.

    # Mock isolation to allow command execution logic to proceed
    with patch("llmc_mcp.isolation.require_isolation") as mock_iso:
        mock_iso.return_value = None

        # Execute 'whoami' (not in allowlist)
        # We pass the blacklist from the loaded config
        result = run_cmd(
            "whoami", cwd=tmp_path, blacklist=config.tools.run_cmd_blacklist
        )

        # The Test: Assert that the security control worked (i.e., blocked the command).
        # THIS ASSERTION IS EXPECTED TO FAIL until the bug is fixed.
        assert (
            result.success is False
        ), f"Security Breach: 'whoami' was allowed despite not being in allowlist! Stdout: {result.stdout.strip()}"
        assert (
            result.error and "Security" in result.error
        ), f"Error should be security related, got: {result.error}"
