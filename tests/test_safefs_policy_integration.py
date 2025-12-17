from __future__ import annotations

from pathlib import Path

import pytest

from llmc.rag_repo.fs import SafeFS
from llmc.rag_repo.policy import PathPolicyError, PathSafetyPolicy


def test_safefs_readonly_blocks_write(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    fs = SafeFS(base, policy=PathSafetyPolicy(readonly=True))
    with pytest.raises(PathPolicyError):
        fs.open_write("file.txt")


def test_safefs_dry_run_rm_tree_returns_plan(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    (base / "a").mkdir()
    (base / "a" / "x.txt").write_text("x")
    fs = SafeFS(base, policy=PathSafetyPolicy(dry_run=True))
    plan = fs.rm_tree("a")
    assert isinstance(plan, dict)
    assert plan["would_delete"]
    # Ensure nothing was actually deleted
    assert (base / "a" / "x.txt").exists()
