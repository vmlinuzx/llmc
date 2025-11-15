"""Workspace planning, initialization, and validation."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

try:
    import yaml  # type: ignore[import]
except Exception:  # pragma: no cover - optional
    yaml = None  # type: ignore[assignment]

from .models import (
    RepoInspection,
    RegistryEntry,
    ToolConfig,
    WorkspacePlan,
    WorkspaceValidationResult,
)
from .utils import canonical_repo_path, generate_repo_id


def plan_workspace(
    repo_root: Path, tool_config: ToolConfig, inspection: RepoInspection
) -> WorkspacePlan:
    if inspection.workspace_path is not None:
        root = inspection.workspace_path
    else:
        root = canonical_repo_path(repo_root) / tool_config.default_workspace_folder_name

    config_dir = root / "config"
    indexes_dir = root / "indexes"
    logs_dir = root / "logs"
    tmp_dir = root / "tmp"

    return WorkspacePlan(
        workspace_root=root,
        config_dir=config_dir,
        indexes_dir=indexes_dir,
        logs_dir=logs_dir,
        tmp_dir=tmp_dir,
        rag_config_path=config_dir / "rag.yml",
        version_config_path=config_dir / "version.yml",
    )


def init_workspace(
    plan: WorkspacePlan,
    inspection: RepoInspection,
    tool_config: ToolConfig,
    non_interactive: bool = False,
) -> None:
    plan.workspace_root.mkdir(parents=True, exist_ok=True)
    plan.config_dir.mkdir(parents=True, exist_ok=True)
    plan.indexes_dir.mkdir(parents=True, exist_ok=True)
    plan.logs_dir.mkdir(parents=True, exist_ok=True)
    plan.tmp_dir.mkdir(parents=True, exist_ok=True)

    if yaml is None:
        raise RuntimeError("PyYAML is required to write workspace configs")

    # rag.yml
    if not plan.rag_config_path.exists():
        repo_id = generate_repo_id(inspection.repo_root)
        rag_config = {
            "repo_id": repo_id,
            "display_name": inspection.repo_root.name,
            "rag_profile": tool_config.default_rag_profile,
            "include_paths": ["."],
            "exclude_paths": [],
            "language_hints": [],
        }
        with plan.rag_config_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(rag_config, f)

    # version.yml
    if not plan.version_config_path.exists():
        version_config = {
            "config_version": "v1",
            "created_at": datetime.utcnow().isoformat(),
        }
        with plan.version_config_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(version_config, f)

    # .gitignore inside workspace
    gitignore = plan.workspace_root / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            "indexes/\nlogs/\ntmp/\n", encoding="utf-8"
        )


def validate_workspace(plan: WorkspacePlan) -> WorkspaceValidationResult:
    issues: list[str] = []
    status = "ok"
    if not plan.config_dir.exists():
        status = "error"
        issues.append("Missing config/ directory in workspace")
    if not plan.rag_config_path.exists():
        status = "error"
        issues.append("Missing rag.yml config file")
    if not plan.version_config_path.exists():
        status = "warning"
        issues.append("Missing version.yml (consider migrating workspace)")

    return WorkspaceValidationResult(status=status, issues=issues, suggested_migrations=[])
