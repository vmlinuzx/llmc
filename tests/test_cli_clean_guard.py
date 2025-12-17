from __future__ import annotations

from pathlib import Path

import pytest

from llmc.rag_repo.cli import clean_workspace


def test_clean_workspace_requires_force(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".llmc" / "workspace").mkdir(parents=True)
    with pytest.raises(RuntimeError):
        clean_workspace(repo, None, force=False)


def test_clean_workspace_with_force(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    ws = repo / ".llmc" / "workspace"
    ws.mkdir(parents=True)
    (ws / "temp.txt").write_text("x")
    result = clean_workspace(repo, None, force=True)
    assert not any(ws.iterdir())
    assert "workspace_root" in result
