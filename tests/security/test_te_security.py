import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from llmc_mcp.tools.te import te_run, PathSecurityError

def test_te_run_rce_fixed():
    """Verify that the RCE vulnerability in te_run is fixed."""
    with patch("subprocess.run") as mock_run:
        # Configure the mock to avoid attribute errors downstream
        mock_result = MagicMock()
        mock_result.stdout = "{}"
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Attempt to exploit the vulnerability
        os.environ["LLMC_TE_EXE"] = "echo"
        te_run(["hello"])
        del os.environ["LLMC_TE_EXE"]

        # Check that the executable is still "te"
        args, _ = mock_run.call_args
        assert args[0][0] == "te"

def test_te_run_cwd_validation():
    """Verify that the cwd validation is working."""
    # Set up a safe directory
    safe_dir = Path("/tmp/safe_dir")
    safe_dir.mkdir(exist_ok=True)
    allowed_roots = [str(safe_dir)]

    # 1. Test case: Attempt to run a command in a disallowed directory
    result = te_run(["ls"], cwd="/", allowed_roots=allowed_roots)

    # Check for the expected error in the returned dictionary
    assert result.get("meta", {}).get("error") is True
    assert "PathSecurityError" in result.get("meta", {}).get("stderr", "")
    assert "outside allowed roots" in result.get("meta", {}).get("stderr", "")

    # 2. Test case: Attempt to run a command in an allowed directory
    with patch("subprocess.run") as mock_run:
        # Configure the mock to return a CompletedProcess-like object
        mock_result = MagicMock()
        mock_result.stdout = '{"some": "json"}'
        mock_result.stderr = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result_allowed = te_run(["ls"], cwd=str(safe_dir), allowed_roots=allowed_roots)

        # Check that it did NOT error out
        assert "error" not in result_allowed.get("meta", {}), f"Unexpected error: {result_allowed.get('meta', {}).get('stderr')}"

        # Check that subprocess.run was called with the correct, resolved cwd
        _, kwargs = mock_run.call_args
        assert "cwd" in kwargs
        assert isinstance(kwargs["cwd"], Path)
        assert str(kwargs["cwd"]) == str(safe_dir.resolve())
