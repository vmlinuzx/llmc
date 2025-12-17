import pytest

from llmc_mcp.tools.fs import PathSecurityError, read_file, validate_path


def test_path_traversal_blocked(tmp_path):
    """
    Verify that path traversal attempts are blocked by validate_path.
    """
    # Setup
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()

    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("TOP SECRET")

    # allowed_roots list
    roots = [str(allowed_root)]

    # 1. Test ".." traversal
    traversal_path = allowed_root / "../secret.txt"
    with pytest.raises(PathSecurityError):
        validate_path(str(traversal_path), roots)

    # 2. Test absolute path outside root
    with pytest.raises(PathSecurityError):
        validate_path(str(secret_file), roots)

    # 3. Test symlink traversal (if symlinks supported)
    try:
        symlink = allowed_root / "link_to_secret"
        symlink.symlink_to(secret_file)

        # It should fail because the *target* is outside allowed roots
        # The code checks `_check_symlink_escape`
        with pytest.raises(PathSecurityError):
            validate_path(str(symlink), roots)

    except OSError:
        # Symlinks might not be supported on all environments
        pass


def test_read_file_traversal(tmp_path):
    """Verify read_file wrapper enforces security."""
    allowed_root = tmp_path / "allowed"
    allowed_root.mkdir()
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("TOP SECRET")
    roots = [str(allowed_root)]

    # Attempt traversal
    result = read_file(str(allowed_root / "../secret.txt"), roots)

    assert result.success is False
    assert "outside allowed roots" in result.error
