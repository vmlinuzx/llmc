"""Data models for the LLMC RAG Daemon."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class DaemonConfig:
    """Runtime configuration for the daemon.

    Values are loaded from a YAML file and then treated as immutable.
    """

    tick_interval_seconds: int
    max_concurrent_jobs: int
    max_consecutive_failures: int
    base_backoff_seconds: int
    max_backoff_seconds: int
    registry_path: Path
    state_store_path: Path
    log_path: Path
    control_dir: Path
    # Optional roots to constrain repo/workspace locations when set.
    repos_root: Path | None = None
    workspaces_root: Path | None = None
    job_runner_cmd: str = "llmc-rag-job"
    log_level: str = "INFO"


@dataclass(frozen=True)
class RepoDescriptor:
    """Description of a repo as read from the repo registry."""

    repo_id: str
    repo_path: Path
    rag_workspace_path: Path
    display_name: str | None = None
    rag_profile: str | None = None
    min_refresh_interval: timedelta | None = None


@dataclass
class RepoState:
    """Daemon-maintained state for a repo."""

    repo_id: str
    last_run_started_at: datetime | None = None
    last_run_finished_at: datetime | None = None
    last_run_status: str = "never"  # never|success|error|skipped|running
    last_error_reason: str | None = None
    consecutive_failures: int = 0
    next_eligible_at: datetime | None = None
    last_job_summary: dict[str, Any] | None = None


@dataclass(frozen=True)
class Job:
    """A scheduled RAG refresh job for a single repo."""

    job_id: str
    repo: RepoDescriptor
    force: bool = False


@dataclass(frozen=True)
class JobResult:
    """Result of executing a job via the job runner."""

    success: bool
    exit_code: int
    error_reason: str | None = None
    summary: dict[str, Any] | None = None
    stdout_tail: str | None = None
    stderr_tail: str | None = None


@dataclass(frozen=True)
class ControlEvents:
    """Control signals read from the control surface."""

    refresh_all: bool = False
    refresh_repo_ids: set[str] = field(default_factory=set)
    shutdown: bool = False




def utc_now() -> datetime:
    """Return timezone-aware now() in UTC."""
    return datetime.now(UTC)
