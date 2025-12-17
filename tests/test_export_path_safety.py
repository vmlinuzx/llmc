from __future__ import annotations

from pathlib import Path

import pytest

from llmc.rag_repo.cli import resolve_export_dir
from llmc.rag_repo.utils import PathTraversalError


def test_resolve_export_dir_ok(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".llmc" / "workspace").mkdir(parents=True)
    out = resolve_export_dir(repo, None, "exports")
    assert out == (repo / ".llmc" / "workspace" / "exports").resolve()


def test_resolve_export_dir_blocks_escape(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".llmc" / "workspace").mkdir(parents=True)
    with pytest.raises(PathTraversalError):
        resolve_export_dir(repo, None, "../../etc")
