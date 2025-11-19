from __future__ import annotations

from pathlib import Path

import pytest

from tools.rag_repo.cli import resolve_workspace_from_cli, resolve_export_dir
from tools.rag_repo.utils import PathTraversalError


def test_cli_helpers_e2e_ok(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".llmc" / "workspace").mkdir(parents=True)
    ws = resolve_workspace_from_cli(repo, None)
    ex = resolve_export_dir(repo, None, "exports")
    assert str(ex).startswith(str(ws))


def test_cli_helpers_e2e_block_escape(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".llmc" / "workspace").mkdir(parents=True)
    with pytest.raises(PathTraversalError):
        resolve_workspace_from_cli(repo, "../outside")

