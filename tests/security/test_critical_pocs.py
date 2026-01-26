from pathlib import Path
import sys
from unittest.mock import patch

import pytest

# Import targets
from llmc.te.cli import _handle_passthrough
from llmc_mcp.tools.te import te_run


def test_te_cli_no_shell_injection():
    """
    Security Test: TE CLI does NOT use shell=True.
    
    Originally a PoC for VULN-001, now verifies the fix.
    The _handle_passthrough function should NOT use shell=True.
    """
    repo_root = Path(".")

    with patch("subprocess.run") as mock_run:
        # Try injection payload
        command = "echo"
        args = ["hello; rm -rf /"]

        _handle_passthrough(command, args, repo_root)

        # Verify call
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        kwargs = call_args[1]

        # Security: shell=True must NOT be used
        assert (
            kwargs.get("shell") is not True
        ), "CRITICAL: TE CLI is still using shell=True for pass-through!"

        print(
            "\n[+] Security Verified: TE CLI uses shell=False, preventing injection"
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
