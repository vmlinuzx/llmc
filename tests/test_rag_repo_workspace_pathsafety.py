from __future__ import annotations

from pathlib import Path
import types

import pytest

from tools.rag_repo import workspace as ws
from tools.rag_repo.utils import PathTraversalError


def _extract_root(result) -> Path:
    """Be flexible about plan_workspace return shapes for future-proofing."""
    if isinstance(result, dict) and "workspace_root" in result:
        return Path(result["workspace_root"])
    if hasattr(result, "workspace_root"):
        return Path(result.workspace_root)
    if hasattr(result, "root"):
        return Path(result.root)
    if isinstance(result, (tuple, list)) and result:
        return Path(result[0])
    if isinstance(result, (str, Path)):
        return Path(result)
    raise AssertionError(f"Unrecognized plan_workspace return shape: {type(result)}")


class ToolConfig(types.SimpleNamespace):
    default_workspace_folder_name: str = ".llmc/workspace"


class Inspection(types.SimpleNamespace):
    workspace_path = None


def test_plan_workspace_normal(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = ToolConfig(default_workspace_folder_name=".llmc/workspace")
    insp = Inspection(workspace_path=None)

    result = ws.plan_workspace(repo, cfg, insp)
    root = _extract_root(result)

    assert root == (repo / ".llmc/workspace").resolve()


def test_plan_workspace_malicious_raises(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = ToolConfig(default_workspace_folder_name=".llmc/workspace")
    insp = Inspection(workspace_path="../outside")

    with pytest.raises(PathTraversalError):
        ws.plan_workspace(repo, cfg, insp)
