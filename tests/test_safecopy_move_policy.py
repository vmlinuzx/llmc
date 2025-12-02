from __future__ import annotations

from pathlib import Path

import pytest

from tools.rag_repo.fs import SafeFS
from tools.rag_repo.policy import PathPolicyError, PathSafetyPolicy


def test_copy_and_move_inside_base(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    (base / "a").mkdir()
    (base / "a" / "f.txt").write_text("x")
    fs = SafeFS(base)
    # copy
    fs.copy_into("a/f.txt", "b/f.txt", overwrite=False)
    assert (base / "b" / "f.txt").read_text() == "x"
    # move
    fs.move_into("b/f.txt", "c/f.txt", overwrite=False)
    assert (base / "c" / "f.txt").read_text() == "x"
    assert not (base / "b" / "f.txt").exists()


def test_copy_respects_readonly(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    (base / "a.txt").write_text("x")
    fs = SafeFS(base, policy=PathSafetyPolicy(readonly=True))
    with pytest.raises(PathPolicyError):
        fs.copy_into("a.txt", "b.txt")
