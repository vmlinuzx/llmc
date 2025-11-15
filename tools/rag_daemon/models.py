"""Data models for the LLMC RAG Daemon."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set


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
    job_runner_cmd: str = "llmc-rag-job"
    log_level: str = "INFO"


@dataclass(frozen=True)
class RepoDescriptor:
    """Description of a repo as read from the repo registry."""

    repo_id: str
    repo_path: Path
    rag_workspace_path: Path
    display_name: Optional[str] = None
    rag_profile: Optional[str] = None
    min_refresh_interval: Optional[timedelta] = None


@dataclass
class RepoState:
    """Daemon-maintained state for a repo."""

    repo_id: str
    last_run_started_at: Optional[datetime] = None
    last_run_finished_at: Optional[datetime] = None
    last_run_status: str = "never"  # never|success|error|skipped|running
    last_error_reason: Optional[str] = None
    consecutive_failures: int = 0
    next_eligible_at: Optional[datetime] = None
    last_job_summary: Optional[Dict[str, Any]] = None


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
    error_reason: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None
    stdout_tail: Optional[str] = None
    stderr_tail: Optional[str] = None


@dataclass(frozen=True)
class ControlEvents:
    """Control signals read from the control surface."""

    refresh_all: bool = False
    refresh_repo_ids: Set[str] = field(default_factory=set)
    shutdown: bool = False


UTC = timezone.utc


def utc_now() -> datetime:
    """Return timezone-aware now() in UTC."""
    return datetime.now(UTC)
