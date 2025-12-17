"""Data models for the repo registration tool."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class ToolConfig:
    registry_path: Path
    default_workspace_folder_name: str = ".llmc/rag"
    default_rag_profile: str = "default"
    daemon_control_path: Path | None = None
    log_level: str = "INFO"


@dataclass
class RepoInspection:
    repo_root: Path
    exists: bool
    has_git: bool
    workspace_path: Path | None
    workspace_status: str  # missing|ok|incomplete|corrupt
    config_version: str | None = None
    issues: list[str] = field(default_factory=list)


@dataclass
class WorkspacePlan:
    workspace_root: Path
    config_dir: Path
    index_dir: Path
    enrichments_dir: Path
    metadata_dir: Path
    logs_dir: Path
    tmp_dir: Path
    rag_config_path: Path
    version_config_path: Path


@dataclass
class WorkspaceValidationResult:
    status: str  # ok|warning|error
    issues: list[str] = field(default_factory=list)
    suggested_migrations: list[str] = field(default_factory=list)


@dataclass
class RegistryEntry:
    repo_id: str
    repo_path: Path
    rag_workspace_path: Path
    display_name: str
    rag_profile: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    min_refresh_interval_seconds: int | None = None
