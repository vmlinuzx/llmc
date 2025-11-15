"""Data models for the repo registration tool."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class ToolConfig:
    registry_path: Path
    default_workspace_folder_name: str = ".llmc/rag"
    default_rag_profile: str = "default"
    daemon_control_path: Optional[Path] = None
    log_level: str = "INFO"


@dataclass
class RepoInspection:
    repo_root: Path
    exists: bool
    has_git: bool
    workspace_path: Optional[Path]
    workspace_status: str  # missing|ok|incomplete|corrupt
    config_version: Optional[str] = None
    issues: List[str] = field(default_factory=list)


@dataclass
class WorkspacePlan:
    workspace_root: Path
    config_dir: Path
    indexes_dir: Path
    logs_dir: Path
    tmp_dir: Path
    rag_config_path: Path
    version_config_path: Path


@dataclass
class WorkspaceValidationResult:
    status: str  # ok|warning|error
    issues: List[str] = field(default_factory=list)
    suggested_migrations: List[str] = field(default_factory=list)


@dataclass
class RegistryEntry:
    repo_id: str
    repo_path: Path
    rag_workspace_path: Path
    display_name: str
    rag_profile: str
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    min_refresh_interval_seconds: Optional[int] = None
