from __future__ import annotations

import os
from pathlib import Path

import pytest

from llmc.rag_repo.utils import PathTraversalError, safe_subpath


def test_safe_subpath_allows_normal_relative(tmp_path: Path) -> None:
    base = tmp_path
    result = safe_subpath(base, "src/main.py")
    assert result == base / "src" / "main.py"
    assert result.is_absolute()


def test_safe_subpath_normalizes_dots(tmp_path: Path) -> None:
    base = tmp_path
    result = safe_subpath(base, "src/../src/main.py")
    assert result == base / "src" / "main.py"


def test_safe_subpath_allows_absolute_inside(tmp_path: Path) -> None:
    base = tmp_path
    target = base / "a" / "b" / "c.txt"
    target.parent.mkdir(parents=True)
    target.touch()
    result = safe_subpath(base, target)
    assert result == target.resolve()


def test_safe_subpath_blocks_parent_escape(tmp_path: Path) -> None:
    base = tmp_path / "root"
    base.mkdir()
    with pytest.raises(PathTraversalError):
        safe_subpath(base, "../../etc/passwd")


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks not supported on this platform")
def test_safe_subpath_blocks_symlink_outside(tmp_path: Path) -> None:
    base = tmp_path / "root"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = base / "link"
    # Ensure symlink doesn't already exist
    if link.exists():
        link.unlink()
    link.symlink_to(outside, target_is_directory=True)

    # Attempt to resolve through the symlink to a file outside base.
    with pytest.raises(PathTraversalError):
        safe_subpath(base, "link/file.txt")
