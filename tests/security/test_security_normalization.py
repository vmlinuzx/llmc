
import pytest
from pathlib import Path
from llmc.security import normalize_path, PathSecurityError

def test_normalize_path_returns_canonical_relative_path(tmp_path):
    """
    Test that normalize_path returns a canonical relative path (no '..' components)
    when the target exists inside the repo.
    """
    repo_root = tmp_path
    (repo_root / "subdir").mkdir()
    (repo_root / "subdir" / "file.txt").write_text("content")

    # Target path with traversal that stays inside repo
    target = "subdir/../subdir/file.txt"

    result = normalize_path(repo_root, target)

    # The result should be "subdir/file.txt", NOT "subdir/../subdir/file.txt"
    assert result == Path("subdir/file.txt")
    assert ".." not in str(result)

def test_normalize_path_bypass_scenario(tmp_path):
    """
    Test a security bypass scenario where a naive prefix check could be bypassed
    if normalize_path returned a non-canonical path.
    """
    repo_root = tmp_path
    (repo_root / "public").mkdir()
    (repo_root / "private").mkdir()
    (repo_root / "private" / "secret.txt").write_text("secret")

    # Attacker tries to access private file via public directory traversal
    target = "public/../private/secret.txt"

    result = normalize_path(repo_root, target)

    # If result is "public/../private/secret.txt", a check for startswith("private") would fail.
    # The result MUST be "private/secret.txt"
    assert result == Path("private/secret.txt")

    # Simulate the vulnerable check
    str_path = str(result)
    is_safe_check = not str_path.startswith("private")

    # If the check thinks it's safe (because it doesn't start with private), fail the test
    # (In this simulation, we want to access private, so if is_safe_check is True, it means we bypassed the block)
    # Wait, the logic is: "Block if starts with private".
    # If result is "public/../private...", it does NOT start with private, so block is bypassed.
    # We want result to be "private/...", so block is triggered.

    assert str_path.startswith("private"), f"Path {str_path} successfully bypassed 'private' prefix check!"

def test_normalize_path_absolute_input(tmp_path):
    repo_root = tmp_path
    (repo_root / "file.txt").write_text("content")

    abs_path = (repo_root / "file.txt").resolve()
    result = normalize_path(repo_root, str(abs_path))

    assert result == Path("file.txt")

def test_normalize_path_traversal_outside(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with pytest.raises(PathSecurityError):
        normalize_path(repo_root, "../outside.txt")

    with pytest.raises(PathSecurityError):
        normalize_path(repo_root, "/etc/passwd")

def test_normalize_path_fuzzy_fallback(tmp_path):
    """
    Test that if exact path doesn't exist, it falls back to fuzzy matching.
    """
    repo_root = tmp_path
    (repo_root / "scripts").mkdir()
    (repo_root / "scripts" / "router.py").write_text("content")

    # router.py exists in scripts/router.py
    # normalize_path(root, "router.py") should find it
    result = normalize_path(repo_root, "router.py")
    assert result == Path("scripts/router.py")
