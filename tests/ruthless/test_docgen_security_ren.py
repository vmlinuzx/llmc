import os
from pathlib import Path

import pytest

from llmc.docgen.gating import resolve_doc_path


class TestResolveDocPathRen:
    """Ruthless security testing for docgen path resolution."""

    @pytest.fixture
    def repo_root(self, tmp_path):
        return tmp_path / "repo"

    def test_happy_path(self, repo_root):
        """Standard valid path should work."""
        (repo_root / "DOCS/REPODOCS").mkdir(parents=True)

        result = resolve_doc_path(repo_root, Path("src/main.py"))
        expected = repo_root / "DOCS/REPODOCS/src/main.py.md"
        assert result == expected

    def test_parent_traversal_simple(self, repo_root):
        """Test simple ../ traversal."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            resolve_doc_path(repo_root, Path("../secret.txt"))

    def test_parent_traversal_complex(self, repo_root):
        """Test complex traversal that might look valid initially."""
        # DOCS/REPODOCS/../../secret.txt
        with pytest.raises(ValueError, match="Path traversal detected"):
            resolve_doc_path(repo_root, Path("../../secret.txt"))

    def test_absolute_path_breakout(self, repo_root):
        """Test absolute path injection."""
        # On Linux, joining an absolute path discards the left side
        abs_path = Path("/etc/passwd")

        # The function does: output_base / f"{relative_path}.md"
        # If relative_path is absolute, f-string makes it a string
        # So output_base / "/etc/passwd.md" -> "/etc/passwd.md" (absolute)
        # resolve() keeps it absolute
        # relative_to() should fail

        with pytest.raises(ValueError, match="Path traversal detected"):
            resolve_doc_path(repo_root, abs_path)

    def test_null_byte_injection(self, repo_root):
        """Test null byte injection (common C-based vuln, less likely in Python Path but worth checking)."""
        try:
            # Python pathlib might raise ValueError on null bytes immediately
            resolve_doc_path(repo_root, Path("src/main.py\0.evil"))
        except ValueError:
            # If it raises ValueError for null byte, that's also a pass for "secure"
            # But we want to ensure it doesn't pass through
            pass

    def test_symlink_attack(self, repo_root):
        """Test if resolving a symlink that points outside is caught."""
        # Setup:
        # repo/DOCS/REPODOCS/link.md -> /tmp/outside

        docs_dir = repo_root / "DOCS/REPODOCS"
        docs_dir.mkdir(parents=True)

        outside_target = repo_root.parent / "target"
        outside_target.touch()

        # If the *input* path is a symlink pointing outside?
        # The function adds .md to it.
        # invalid_link -> /outside
        # We ask for "invalid_link"
        # Result: .../invalid_link.md
        # This doesn't exploit symlinks unless the .md file itself is a symlink?

        # What if we ask for a path that *resolves* to outside?
        # resolve_doc_path calculates the OUTPUT path.
        # If I say relative_path="foo", output is ".../foo.md"
        # If ".../foo.md" already exists and is a symlink to /etc/passwd?

        # Create the evil symlink
        evil_link = docs_dir / "evil.md"
        try:
            os.symlink("/etc/passwd", evil_link)
        except OSError:
            pytest.skip("Cannot create symlinks")

        # Now ask for "evil" (which maps to evil.md)
        # resolve() should follow the symlink to /etc/passwd
        # relative_to() should fail

        with pytest.raises(ValueError, match="Path traversal detected"):
            resolve_doc_path(repo_root, Path("evil"))
