"""
POC for Isolation Bypass Vulnerabilities.

Demonstrates:
1. VULN-002: LLMC_ISOLATED=1 environment variable bypasses isolation checks.
2. VULN-003: `te run` CLI command executes subprocesses without enforcing isolation.
"""

import os
from pathlib import Path
import subprocess
from unittest.mock import patch, MagicMock
import pytest

# Import targets
try:
    from llmc_mcp.tools.cmd import run_cmd
    from llmc_mcp.isolation import is_isolated_environment
    from llmc.te.cli import _handle_passthrough
except ImportError:
    pytest.skip("LLMC modules not found", allow_module_level=True)


def test_vuln_002_isolation_bypass_env_var(tmp_path):
    """
    VULN-002: Prove that setting LLMC_ISOLATED=1 allows run_cmd to execute
    even when the environment is NOT actually isolated.
    """
    # 1. Verify that without the env var, it fails (assuming we are not in a container)
    # We force is_isolated_environment to return False first (by mocking the underlying checks if needed)
    # But wait, is_isolated_environment checks the env var itself.

    # We clear the cache to ensure we get a fresh result
    is_isolated_environment.cache_clear()

    # Ensure env var is NOT set
    if "LLMC_ISOLATED" in os.environ:
        del os.environ["LLMC_ISOLATED"]

    # We assume the test runner is NOT in a container (or we mock it to look like one is not)
    # To be robust, we mock the file/env checks inside is_isolated_environment to return False
    with patch("pathlib.Path.exists", return_value=False), \
         patch.dict(os.environ, clear=True):

        # Verify it returns False
        assert is_isolated_environment() is False

        # Calling run_cmd should fail
        result = run_cmd("echo should_fail", cwd=tmp_path)
        assert not result.success
        assert "requires an isolated environment" in (result.error or "")

    # 2. Now set LLMC_ISOLATED=1 and verify it passes
    is_isolated_environment.cache_clear()
    with patch.dict(os.environ, {"LLMC_ISOLATED": "1"}):
        # It should now return True
        assert is_isolated_environment() is True

        # run_cmd should succeed
        result = run_cmd("echo BYPASSED", cwd=tmp_path)
        assert result.success
        assert "BYPASSED" in result.stdout


def test_vuln_003_te_run_no_isolation(tmp_path):
    """
    VULN-003: Prove that `te run` (_handle_passthrough) executes commands
    without calling require_isolation, thus bypassing the security model.
    """
    # We mock subprocess.run to avoid actual execution but verify it was called
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "executed"
        mock_run.return_value.stderr = ""

        # Call _handle_passthrough directly
        # It should NOT call is_isolated_environment or require_isolation

        with patch("llmc_mcp.isolation.is_isolated_environment") as mock_iso:
            mock_iso.return_value = False # Pretend we are NOT isolated

            _handle_passthrough(
                "echo",
                ["INSECURE"],
                repo_root=Path("/tmp"),
                json_mode=False
            )

            # Verify subprocess.run was called
            mock_run.assert_called()
            args = mock_run.call_args[0][0]
            assert args == ["echo", "INSECURE"]

            # Verify require_isolation was NOT called (implied by success despite mock_iso=False)
            # If it had checked isolation, it would have failed/raised/checked the mock.
            # Since _handle_passthrough doesn't import isolation, this confirms the vuln.
