import pytest
from unittest.mock import patch, MagicMock
from llmc_mcp.tools.te import te_run

def test_te_run_bypasses_isolation():
    """
    VULNERABILITY CONFIRMATION:
    Verify that te_run does NOT call require_isolation, allowing command execution
    even in non-isolated environments.
    """
    # We mock subprocess.run to avoid actual execution
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "{}"
        mock_run.return_value.returncode = 0

        # We also mock require_isolation to fail if called
        # But wait, te_run doesn't import require_isolation.
        # So we can't easily assert it's NOT called by mocking it there.
        # But we can check if it works without isolation.

        # Ensure is_isolated_environment returns False
        with patch("llmc_mcp.isolation.is_isolated_environment", return_value=False):
            # And ensure require_isolation would raise if called
            with patch("llmc_mcp.isolation.require_isolation", side_effect=RuntimeError("ISOLATION REQUIRED")):

                # Execute te_run
                # It should call subprocess.run("te", ...)
                try:
                    te_run(["run", "echo", "hacked"])
                except RuntimeError as e:
                    if "ISOLATION REQUIRED" in str(e):
                        pytest.fail("te_run unexpectedly called require_isolation (Secure)")
                    else:
                        raise e

                # If we get here, it succeeded without raising RuntimeError
                assert mock_run.called
                args = mock_run.call_args[0][0]
                assert args[0] == "te"
                assert "run" in args
                assert "echo" in args
