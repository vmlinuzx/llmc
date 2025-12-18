import pytest
from pathlib import Path
from llmc_mcp.tools.fs import validate_path, PathSecurityError

def test_empty_allowed_roots_allows_everything(tmp_path):
    """
    VULNERABILITY CONFIRMATION:
    Verify that empty allowed_roots list grants full filesystem access.
    """
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("TOP SECRET")

    # Empty allowed_roots = Full Access
    roots = []

    # Should succeed
    try:
        resolved = validate_path(str(secret_file), roots)
        assert resolved == secret_file.resolve()
    except PathSecurityError:
        pytest.fail("Empty allowed_roots should allow access (per SDD/Code), but it blocked it.")

def test_root_allowed_allows_everything(tmp_path):
    """
    VULNERABILITY CONFIRMATION:
    Verify that '/' in allowed_roots grants full filesystem access.
    """
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("TOP SECRET")

    roots = ["/"]

    # Should succeed
    try:
        resolved = validate_path(str(secret_file), roots)
        assert resolved == secret_file.resolve()
    except PathSecurityError:
        pytest.fail("'/' in allowed_roots should allow access, but it blocked it.")
