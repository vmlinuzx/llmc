from __future__ import annotations

from pathlib import Path

import pytest

from llmc.rag_daemon import api as dapi, registry as dreg
from llmc.rag_repo.utils import PathTraversalError


class Cfg:
    def __init__(self) -> None:
        self.repos_root: Path | None = None
        self.workspaces_root: Path | None = None


def test_daemon_normalize_and_validate(tmp_path: Path) -> None:
    cfg = Cfg()
    cfg.repos_root = tmp_path / "repos"
    cfg.workspaces_root = tmp_path / "workspaces"
    cfg.repos_root.mkdir()
    cfg.workspaces_root.mkdir()
    (cfg.repos_root / "proj").mkdir()
    (cfg.repos_root / "proj" / "repoA").mkdir()
    (cfg.workspaces_root / "ws").mkdir()
    (cfg.workspaces_root / "ws" / "repoA").mkdir()
    r, w = dreg._normalize_paths(cfg, "proj/repoA", "ws/repoA")
    assert str(r).startswith(str(cfg.repos_root))
    assert str(w).startswith(str(cfg.workspaces_root))
    r2, w2 = dapi.validate_job_paths(cfg, "proj/repoA", "ws/repoA")
    assert str(r2).startswith(str(cfg.repos_root))
    assert str(w2).startswith(str(cfg.workspaces_root))


def test_daemon_rejects_outside(tmp_path: Path) -> None:
    cfg = Cfg()
    cfg.repos_root = tmp_path / "repos"
    cfg.repos_root.mkdir()
    with pytest.raises(PathTraversalError):
        dreg._normalize_paths(cfg, "../../etc", None)
