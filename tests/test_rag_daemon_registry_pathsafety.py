from __future__ import annotations

from pathlib import Path
import types

import pytest

from tools.rag_daemon import registry as dreg
from tools.rag_repo.utils import PathTraversalError


class Cfg(types.SimpleNamespace):
    repos_root = None
    workspaces_root = None


def test_normalize_paths_with_roots(tmp_path: Path) -> None:
    cfg = Cfg()
    cfg.repos_root = tmp_path / "rroot"
    cfg.workspaces_root = tmp_path / "wroot"
    cfg.repos_root.mkdir()
    cfg.workspaces_root.mkdir()

    repo_rel = "project/repoA"
    ws_rel = "workspaces/repoA"
    (cfg.repos_root / "project").mkdir()
    (cfg.repos_root / "project" / "repoA").mkdir()
    (cfg.workspaces_root / "workspaces").mkdir()
    (cfg.workspaces_root / "workspaces" / "repoA").mkdir()

    repo_path, ws_path = dreg._normalize_paths(cfg, repo_rel, ws_rel)
    assert str(repo_path).startswith(str(cfg.repos_root))
    assert str(ws_path).startswith(str(cfg.workspaces_root))


def test_normalize_paths_rejects_outside(tmp_path: Path) -> None:
    cfg = Cfg()
    cfg.repos_root = tmp_path / "rroot"
    cfg.repos_root.mkdir()

    with pytest.raises(PathTraversalError):
        dreg._normalize_paths(cfg, "../../etc", None)

