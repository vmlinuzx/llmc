from datetime import UTC, datetime, timedelta
from pathlib import Path

from llmc.rag_daemon.models import DaemonConfig, RepoDescriptor, RepoState
from llmc.rag_daemon.registry import RegistryClient
from llmc.rag_daemon.scheduler import Scheduler
from llmc.rag_daemon.state_store import StateStore
from llmc.rag_daemon.workers import WorkerPool


class DummyRegistry(RegistryClient):
    def __init__(self, entries, path: Path) -> None:
        self._entries = entries
        self.path = path

    def load(self):
        return self._entries


class DummyWorkers(WorkerPool):
    def __init__(self, config, state_store):
        super().__init__(config, state_store)
        self.scheduled = []

    def submit_jobs(self, jobs):
        self.scheduled.extend(list(jobs))


def make_config(tmp_path: Path) -> DaemonConfig:
    return DaemonConfig(
        tick_interval_seconds=60,
        max_concurrent_jobs=2,
        max_consecutive_failures=3,
        base_backoff_seconds=60,
        max_backoff_seconds=3600,
        registry_path=tmp_path / "repos.yml",
        state_store_path=tmp_path / "state",
        log_path=tmp_path / "logs",
        control_dir=tmp_path / "control",
    )


def test_scheduler_eligibility_basics(tmp_path: Path) -> None:
    cfg = make_config(tmp_path)
    state_store = StateStore(cfg.state_store_path)

    now = datetime.now(UTC)

    repo = RepoDescriptor(
        repo_id="repo-1",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )
    entries = {"repo-1": repo}
    registry = DummyRegistry(entries, cfg.registry_path)
    workers = DummyWorkers(cfg, state_store)

    scheduler = Scheduler(cfg, registry, state_store, workers)

    eligible = scheduler._is_repo_eligible(repo, None, now, force=False)
    assert eligible is True

    state = RepoState(repo_id="repo-1", last_run_status="success", last_run_finished_at=now)
    later = now + timedelta(seconds=10)
    ineligible = scheduler._is_repo_eligible(repo, state, later, force=False)
    assert ineligible is False
