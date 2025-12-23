import pytest
from pathlib import Path
from llmc.security import normalize_path, PathSecurityError

@pytest.fixture
def repo_root(tmp_path):
    """Fixture to create a temporary repository root."""
    root = tmp_path / "repo"
    root.mkdir()
    return root

def test_normalize_path_null_byte(repo_root):
    """Test that null byte injection raises PathSecurityError."""
    with pytest.raises(PathSecurityError, match="Path contains null bytes"):
        normalize_path(repo_root, "some\x00path")

def test_normalize_path_absolute_traversal(repo_root):
    """Test that absolute path traversal raises PathSecurityError."""
    # Create a path that is definitely outside repo_root
    outside_path = "/etc/passwd"
    
    with pytest.raises(PathSecurityError, match="outside repository boundary"):
        normalize_path(repo_root, outside_path)

def test_normalize_path_traversal(repo_root):
    """Test that relative path traversal raises PathSecurityError."""
    with pytest.raises(PathSecurityError, match="escapes repository boundary"):
        normalize_path(repo_root, "../outside")

def test_normalize_path_fuzzy_malicious(repo_root):
    """Test fuzzy suffix matching with malicious input."""
    # This input attempts to traverse out. It should be caught before fuzzy matching
    # or during fuzzy matching if it were to proceed.
    with pytest.raises(PathSecurityError, match="escapes repository boundary"):
        normalize_path(repo_root, "subdir/../../outside")
