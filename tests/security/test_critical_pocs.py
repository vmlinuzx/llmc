from pathlib import Path
import sys
from unittest.mock import patch

import pytest

# Import targets
from llmc.te.cli import _handle_passthrough
from llmc_mcp.tools.te import te_run


def test_te_cli_command_injection():
    """
    VULN-001 PoC: Command Injection in TE CLI.
    The _handle_passthrough function uses shell=True with user-controlled input.
    """
    repo_root = Path(".")

    # We mock subprocess.run to verify it receives the injected command with shell=True
    with patch("subprocess.run") as mock_run:
        # Simulate 'te run echo "hello; rm -rf /"'
        # The 'te' CLI parses this into command="echo", args=["hello; rm -rf /"]
        command = "echo"
        args = ["hello; rm -rf /"]

        _handle_passthrough(command, args, repo_root)

        # Verify call
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        cmd_arg = call_args[0][0]
        kwargs = call_args[1]

        # Check 1: shell=True is used
        assert (
            kwargs.get("shell") is True
        ), "CRITICAL: TE CLI must not use shell=True for pass-through"

        # Check 2: Malicious payload is present in the command string
        assert "rm -rf /" in cmd_arg, "CRITICAL: Injected command was lost"

        print(
            f"\n[+] Vulnerability Confirmed: TE CLI executes '{cmd_arg}' with shell=True"
        )


def test_te_run_isolation_bypass():
    """
    VULN-002 PoC: MCP te_run tool bypasses isolation checks.
    Unlike run_cmd, te_run does not call require_isolation().
    """
    # Mock subprocess.run so we don't actually try to run 'te'
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "{}"
        mock_run.return_value.returncode = 0

        # Call te_run
        # If it had isolation, it would fail here (assuming we are not in a container)
        # We can also patch require_isolation to fail explicitly to be sure

        with patch(
            "llmc_mcp.isolation.require_isolation",
            side_effect=RuntimeError("Isolation Required!"),
        ) as mock_iso:
            try:
                te_run(["run", "echo", "hello"])
            except RuntimeError:
                pytest.fail(
                    "te_run called require_isolation() - it is secure (unexpected)."
                )

            # If we get here, no exception was raised
            assert (
                not mock_iso.called
            ), "te_run called require_isolation (unexpectedly secure)"
            print("\n[+] Vulnerability Confirmed: te_run does not enforce isolation")


if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
