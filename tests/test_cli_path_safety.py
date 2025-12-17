from __future__ import annotations

from pathlib import Path

import pytest

from llmc.rag_repo.cli import resolve_workspace_from_cli
from llmc.rag_repo.utils import PathTraversalError


def test_resolve_workspace_from_cli_ok(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    ws = resolve_workspace_from_cli(repo, ".llmc/work")
    assert ws == (repo / ".llmc/work").resolve()


def test_resolve_workspace_from_cli_default(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    ws = resolve_workspace_from_cli(repo, None)
    assert ws == (repo / ".llmc/workspace").resolve()


def test_resolve_workspace_from_cli_raises(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(PathTraversalError):
        resolve_workspace_from_cli(repo, "../../etc")
