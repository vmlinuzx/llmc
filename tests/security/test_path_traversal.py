"""
Security tests for path traversal vulnerabilities.

These tests verify that malicious path inputs are properly blocked.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import Mock

from llmc.docgen.gating import validate_source_path
from llmc.docgen.orchestrator import DocgenOrchestrator


def test_path_traversal_basic(tmp_path):
    """Test basic directory traversal attempts are blocked."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    malicious_paths = [
        "../../../../etc/passwd",
        "../../../root/.ssh/id_rsa",
        # "..\\..\\..\\windows\\system32\\config\\sam", # Windows-specific, valid filename on Linux
        "/etc/shadow",
        "/dev/zero",
    ]
    
    for malicious_path in malicious_paths:
        with pytest.raises(ValueError, match="Path traversal|Absolute paths"):
            validate_source_path(repo_root, Path(malicious_path))


def test_symlink_traversal(tmp_path):
    """Test that symlinks can't be used for traversal."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Create file outside repo
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("TOP SECRET")

    # Create symlink inside repo pointing to it
    symlink = repo_root / "evil_link.py"
    try:
        os.symlink(secret_file, symlink)
    except OSError:
        pytest.skip("Symlinks not supported on this platform")

    # Verify it's blocked
    with pytest.raises(ValueError, match="outside repository root"):
        validate_source_path(repo_root, Path("evil_link.py"))

    # Test symlinked directory
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    symlink_dir = repo_root / "evil_dir_link"
    try:
        os.symlink(outside_dir, symlink_dir)
    except OSError:
        pytest.skip("Symlinks not supported on this platform")

    with pytest.raises(ValueError, match="outside repository root"):
        validate_source_path(repo_root, Path("evil_dir_link"))


def test_relative_path_normalization(tmp_path):
    """Test that paths are normalized before validation."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "valid").mkdir()

    tricky_paths = [
        "valid/../../../etc/passwd",
        "./././../../../etc/passwd",
        "valid/./../../etc/passwd",
        # Extended tricky paths to verify normalization
        "valid/..//..//etc/passwd",
        "valid/../../../../../../../../../../etc/passwd",
        "./.././../etc/passwd",
        "valid/./.././../../etc/passwd",
    ]
    
    for path in tricky_paths:
        # Verify that the path is blocked after normalization
        with pytest.raises(ValueError, match="outside repository root|Invalid path resolution"):
            validate_source_path(repo_root, Path(path))


def test_null_byte_injection(tmp_path):
    """Test null byte injection in paths is blocked."""
    repo_root = tmp_path

    null_byte_paths = [
        "valid.txt\x00../../../../etc/passwd",
        "file.py\x00.txt",
    ]
    
    for path in null_byte_paths:
        with pytest.raises(ValueError, match="Null byte"):
            validate_source_path(repo_root, Path(path))


def test_absolute_path_outside_repo(tmp_path):
    """Test absolute paths outside repo are rejected."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    absolute_paths = [
        "/etc/passwd",
        "/root/.ssh/id_rsa",
        "/tmp/evil",
    ]
    
    for path in absolute_paths:
        with pytest.raises(ValueError, match="Absolute paths not allowed"):
            validate_source_path(repo_root, Path(path))


class TestDocgenPathSecurity:
    """
    Security tests for docgen path handling.
    
    These tests verify that malicious paths cannot:
    1. Read files outside repository
    2. Write files outside output directory
    3. Execute scripts outside allowed directory
    """
    
    def test_source_path_traversal_blocked(self, tmp_path):
        """Docgen should block reading files via path traversal."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        # Mock backend and DB
        backend = Mock()
        db = Mock()

        orchestrator = DocgenOrchestrator(
            repo_root=repo_root,
            backend=backend,
            db=db,
            output_dir="docs",
            require_rag_fresh=False
        )

        # Attempt traversal
        result = orchestrator.process_file(Path("../../../../etc/passwd"))

        assert result.status == "skipped"
        assert "Security validation failed" in result.reason
    
    def test_symlink_reading_blocked(self, tmp_path):
        """Docgen should block reading files via symlinks."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        secret = tmp_path / "secret.txt"
        secret.write_text("secret")

        symlink = repo_root / "link.py"
        try:
            os.symlink(secret, symlink)
        except OSError:
            pytest.skip("Symlinks not supported")

        orchestrator = DocgenOrchestrator(
            repo_root=repo_root,
            backend=Mock(),
            db=Mock(),
            output_dir="docs",
            require_rag_fresh=False
        )

        result = orchestrator.process_file(Path("link.py"))

        assert result.status == "skipped"
        assert "Security validation failed" in result.reason
        assert "outside repository root" in result.reason
