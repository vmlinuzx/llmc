from __future__ import annotations

import types
from pathlib import Path

import pytest

from tools.rag_daemon import api as dapi


class Cfg(types.SimpleNamespace):
    repos_root = None
    workspaces_root = None


def test_purge_requires_force(tmp_path: Path) -> None:
    cfg = Cfg()
    cfg.workspaces_root = tmp_path / "wroot"
    cfg.workspaces_root.mkdir()
    (cfg.workspaces_root / "wsA").mkdir()
    with pytest.raises(RuntimeError):
        dapi.purge_workspace(cfg, "wsA", force=False)


def test_purge_with_force(tmp_path: Path) -> None:
    cfg = Cfg()
    cfg.workspaces_root = tmp_path / "wroot"
    cfg.workspaces_root.mkdir()
    ws = cfg.workspaces_root / "wsA"
    ws.mkdir()
    (ws / "junk.txt").write_text("x")
    result = dapi.purge_workspace(cfg, "wsA", force=True)
    assert not any(ws.iterdir())
    assert "workspace_root" in result

