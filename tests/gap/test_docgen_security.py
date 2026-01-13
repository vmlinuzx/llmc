from pathlib import Path
import tempfile
from unittest.mock import MagicMock

import pytest

from llmc_mcp.docgen_guard import DocgenCoordinator


def test_docgen_out_of_bounds_access():
    """
    SDD: tests/gap/SDDs/SDD-Docgen-Security.md

    Test that DocgenCoordinator prevents access to files outside the repository.
    This test targets the Arbitrary File Read vulnerability.
    """
    # 1. Setup paths
    with tempfile.TemporaryDirectory() as temp_dir:
        base = Path(temp_dir)
        repo_root = base / "repo"
        repo_root.mkdir()

        # Create a file OUTSIDE the repo root
        secret_file = base / "secret.txt"
        secret_file.write_text("TEST_FIXTURE_SECRET_DO_NOT_LEAK")

        # 2. Initialize Coordinator
        maasl_mock = MagicMock()
        # Mock the lock call to just execute the op
        maasl_mock.call_with_stomp_guard.side_effect = lambda op, **kwargs: op()

        coordinator = DocgenCoordinator(maasl_mock, str(repo_root))

        # 3. Attempt to access the outside file
        # This SHOULD raise an exception (ValueError or PermissionError)
        # if the security gap is closed.
        # Until fixed, this test is expected to FAIL.
        msg = "DocgenCoordinator allowed access to file outside repository root"

        # We accept either ValueError or PermissionError
        with pytest.raises(
            (ValueError, PermissionError), match=".*within repository.*"
        ):
            coordinator.docgen_file(
                source_path=str(secret_file),
                agent_id="test-agent",
                session_id="test-session",
            )
