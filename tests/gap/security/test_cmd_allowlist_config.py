from unittest.mock import patch
import pytest
from llmc_mcp.config import load_config
from llmc_mcp.tools.cmd import run_cmd


def test_cmd_allowlist_config_mismatch(tmp_path):
    """
    Test that the 'run_cmd_allowlist' in llmc.toml is correctly enforced,
    preventing commands not in the allowlist from executing.
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

    # Check that the config object has the allowlist field
    assert hasattr(
        config.tools, "run_cmd_allowlist"
    ), "Config model is missing 'run_cmd_allowlist'"
    assert config.tools.run_cmd_allowlist == ["ls", "echo"]

    # 4. Execution Test
    # We try to run a command that is NOT in the allowlist (e.g., 'whoami').
    # Desired behavior: It should be blocked.

    # Mock isolation to allow command execution logic to proceed
    with patch("llmc_mcp.isolation.require_isolation") as mock_iso:
        mock_iso.return_value = None

        # Execute 'whoami' (not in allowlist)
        # We pass the allowlist from the loaded config
        result = run_cmd(
            "whoami",
            cwd=tmp_path,
            blacklist=config.tools.run_cmd_blacklist,
            allowlist=config.tools.run_cmd_allowlist
        )

        # The Test: Assert that the security control worked (i.e., blocked the command).
        assert (
            result.success is False
        ), f"Security Breach: 'whoami' was allowed despite not being in allowlist! Stdout: {result.stdout.strip()}"
        assert (
            result.error and "not in allowlist" in result.error
        ), f"Error should mention allowlist, got: {result.error}"

        # 5. Success Test
        # We try to run a command that IS in the allowlist (e.g., 'echo')
        result_allowed = run_cmd(
            "echo hello",
            cwd=tmp_path,
            blacklist=config.tools.run_cmd_blacklist,
            allowlist=config.tools.run_cmd_allowlist
        )
        assert result_allowed.success is True
        assert result_allowed.stdout.strip() == "hello"
