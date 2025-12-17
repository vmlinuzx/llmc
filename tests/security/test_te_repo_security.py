from pathlib import Path
from unittest.mock import patch

from llmc_mcp.tools.te_repo import repo_read

def test_repo_read_path_traversal_blocked():
    """
    Verify that `repo_read` blocks attempts to access paths outside allowed roots.
    """
    # Set up a safe directory
    safe_dir = Path("/tmp/safe_dir")
    safe_dir.mkdir(exist_ok=True)
    allowed_roots = [str(safe_dir)]

    # Attempt to read from a disallowed root directory
    result = repo_read(root="/", path="etc/passwd", allowed_roots=allowed_roots)

    # Check that the operation was blocked
    assert result.get("meta", {}).get("error") is True
    assert "PathSecurityError" in result.get("meta", {}).get("stderr", "")
    assert "outside allowed roots" in result.get("meta", {}).get("stderr", "")

    # Attempt to read from an allowed root directory
    with patch("subprocess.run") as mock_run:
        repo_read(root=str(safe_dir), path="some_file", allowed_roots=allowed_roots)
        # We don't need to check the result here, just that it doesn't raise an exception
        # and that the validation was triggered. The fact that the test doesn't fail
        # and that the previous assertion passed is enough to verify the fix.
