import os
from pathlib import Path

import pytest

from llmc.security import PathSecurityError, normalize_path


def test_normalize_path_basic_traversal(tmp_path):
    """
    Test that basic traversal attempts (../) are rejected.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # Target file strictly outside the repo
    target = "../../../etc/passwd"
    
    with pytest.raises(PathSecurityError):
        normalize_path(repo_root, target)

    # Another variation
    target_2 = "../outside_file"
    with pytest.raises(PathSecurityError):
        normalize_path(repo_root, target_2)

def test_normalize_path_absolute_path_traversal(tmp_path):
    """
    Test that absolute paths outside the repo_root are rejected.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # Create a file outside the repo
    outside_file = tmp_path / "outside_file"
    outside_file.touch()
    
    with pytest.raises(PathSecurityError):
        normalize_path(repo_root, str(outside_file))

def test_normalize_path_symlink_traversal(tmp_path):
    """
    Test that symlinks resolving to outside the repo_root are rejected.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # 1. Create a file outside the repo_root
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    secret_file = outside_dir / "secret.txt"
    secret_file.touch()
    
    # 2. Create a symlink inside the repo_root pointing to the external file
    symlink_path = repo_root / "link_to_secret"
    os.symlink(secret_file, symlink_path)
    
    # 3. Pass the path of the symlink to normalize_path
    # Note: We pass the filename of the symlink
    with pytest.raises(PathSecurityError):
        normalize_path(repo_root, "link_to_secret")

def test_normalize_path_null_byte_injection(tmp_path):
    """
    Test that paths containing null bytes are rejected.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    target = "some/path\x00/evil"
    
    with pytest.raises(PathSecurityError):
        normalize_path(repo_root, target)

def test_normalize_path_legitimate_paths(tmp_path):
    """
    Test that valid paths within the repo_root are accepted.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # Create some structure
    src_dir = repo_root / "src"
    src_dir.mkdir()
    main_py = src_dir / "main.py"
    main_py.touch()
    
    # Case 1: Relative path
    result = normalize_path(repo_root, "src/main.py")
    assert result == Path("src/main.py")
    
    # Case 2: Absolute path (inside repo)
    result_abs = normalize_path(repo_root, str(main_py.resolve()))
    assert result_abs == Path("src/main.py")
    
    # Case 3: Simple file in root
    root_file = repo_root / "README.md"
    root_file.touch()
    result_root = normalize_path(repo_root, "README.md")
    assert result_root == Path("README.md")

def test_fuzzy_match_resolves_by_shortest_path(tmp_path):
    """
    Test that fuzzy matching resolves ambiguity by preferring the shortest path.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # Create structure:
    # repo_root/a/ambiguous.txt
    # repo_root/b/c/ambiguous.txt
    
    dir_a = repo_root / "a"
    dir_a.mkdir()
    (dir_a / "ambiguous.txt").touch()
    
    dir_b_c = repo_root / "b" / "c"
    dir_b_c.mkdir(parents=True)
    (dir_b_c / "ambiguous.txt").touch()
    
    # Call normalize_path with the filename
    result = normalize_path(repo_root, "ambiguous.txt")
    
    # Expect 'a/ambiguous.txt' (shortest path)
    assert result == Path("a/ambiguous.txt")

def test_fuzzy_match_resolves_alphabetically_on_same_length(tmp_path):
    """
    Test that fuzzy matching resolves ambiguity alphabetically when paths have the same length.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # Create structure:
    # repo_root/x/ambiguous.txt
    # repo_root/z/ambiguous.txt
    
    dir_x = repo_root / "x"
    dir_x.mkdir()
    (dir_x / "ambiguous.txt").touch()
    
    dir_z = repo_root / "z"
    dir_z.mkdir()
    (dir_z / "ambiguous.txt").touch()
    
    # Call normalize_path with the filename
    result = normalize_path(repo_root, "ambiguous.txt")
    
    # Expect 'x/ambiguous.txt' (alphabetical winner between x and z)
    assert result == Path("x/ambiguous.txt")
