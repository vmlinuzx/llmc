from __future__ import annotations

from pathlib import Path
import types

import pytest

from tools.rag_daemon import api as dapi
from tools.rag_repo.utils import PathTraversalError


class Cfg(types.SimpleNamespace):
    repos_root = None
    workspaces_root = None


def test_validate_job_paths_with_roots(tmp_path: Path) -> None:
    cfg = Cfg()
    cfg.repos_root = tmp_path / "rroot"
    cfg.workspaces_root = tmp_path / "wroot"
    cfg.repos_root.mkdir()
    cfg.workspaces_root.mkdir()

    (cfg.repos_root / "proj").mkdir()
    (cfg.repos_root / "proj" / "repoA").mkdir()
    (cfg.workspaces_root / "ws").mkdir()
    (cfg.workspaces_root / "ws" / "repoA").mkdir()

    repo_path, ws_path = dapi.validate_job_paths(cfg, "proj/repoA", "ws/repoA")
    assert str(repo_path).startswith(str(cfg.repos_root))
    assert str(ws_path).startswith(str(cfg.workspaces_root))


def test_validate_job_paths_rejects_repo_outside(tmp_path: Path) -> None:
    cfg = Cfg()
    cfg.repos_root = tmp_path / "rroot"
    cfg.repos_root.mkdir()
    with pytest.raises(PathTraversalError):
        dapi.validate_job_paths(cfg, "../../etc", None)
