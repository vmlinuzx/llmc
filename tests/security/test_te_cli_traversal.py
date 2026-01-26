"""
Security test for Tool Envelope (TE) CLI path traversal vulnerability.
"""

from unittest.mock import patch

import pytest

from llmc.te.cli import main


def test_te_repo_read_traversal_blocked(tmp_path):
    """
    Verify that 'te repo read' blocks path traversal attempts.

    This test mocks the CLI arguments to simulate:
    te repo read --root /tmp/repo --path ../../etc/passwd

    It asserts that the underlying 'cat' command is NOT executed with the
    traversed path.
    """
    # Setup mock repo root
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # We want to try to access ../secret.txt
    target_path = "../secret.txt"

    # Simulate arguments
    # sys.argv[0] is program name
    test_args = ["te", "repo", "read", "--root", str(repo_root), "--path", target_path]

    with patch("sys.argv", test_args), \
         patch("llmc.te.cli._handle_passthrough") as mock_passthrough:

        # Run main
        ret = main()

        # If the vulnerability exists, _handle_passthrough is called.
        if mock_passthrough.called:
            args = mock_passthrough.call_args
            # Signature: _handle_passthrough(command, args, repo_root, ...)
            # args[0] is command ('cat')
            # args[1] is cmd_args (list of paths)
            cmd_args = args[0][1]
            passed_path = cmd_args[0]

            # Fail the test if we allowed access
            pytest.fail(f"Security Vulnerability Detected: Allowed access to {passed_path}")

        # If not called, we expect return code 1 (error)
        assert ret == 1
