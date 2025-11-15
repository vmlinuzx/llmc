"""Repo inspection utilities."""

from __future__ import annotations

from pathlib import Path

from .models import RepoInspection, ToolConfig
from .utils import canonical_repo_path, is_git_repo


def inspect_repo(repo_path: Path, tool_config: ToolConfig) -> RepoInspection:
    repo_root = canonical_repo_path(repo_path)
    exists = repo_root.is_dir()
    if not exists:
        return RepoInspection(
            repo_root=repo_root,
            exists=False,
            has_git=False,
            workspace_path=None,
            workspace_status="missing",
            issues=["Repository path does not exist"],
        )

    has_git = is_git_repo(repo_root)
    workspace_path = repo_root / tool_config.default_workspace_folder_name

    workspace_status = "missing"
    issues: list[str] = []
    config_version = None

    if workspace_path.exists():
        config_dir = workspace_path / "config"
        rag_config = config_dir / "rag.yml"
        version_config = config_dir / "version.yml"
        if rag_config.exists() and version_config.exists():
            workspace_status = "ok"
        else:
            workspace_status = "incomplete"
            if not rag_config.exists():
                issues.append("Missing rag.yml in workspace config/")
            if not version_config.exists():
                issues.append("Missing version.yml in workspace config/")
    else:
        workspace_path = None

    return RepoInspection(
        repo_root=repo_root,
        exists=True,
        has_git=has_git,
        workspace_path=workspace_path,
        workspace_status=workspace_status,
        config_version=config_version,
        issues=issues,
    )
