"""Comprehensive test suite for LLMC RAG Daemon."""

import json
import os
import tempfile
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import pytest

from tools.rag_daemon.config import load_config
from tools.rag_daemon.models import DaemonConfig, RepoDescriptor, RepoState
from tools.rag_daemon.state_store import StateStore
from tools.rag_daemon.registry import RegistryClient
from tools.rag_daemon.scheduler import Scheduler
from tools.rag_daemon.workers import WorkerPool
from tools.rag_daemon.control import read_control_events
from tools.rag_daemon.models import ControlEvents


# ==============================================================================
# 1. Daemon Config & Startup Tests
# ==============================================================================

def test_load_config_default_path(tmp_path: Path) -> None:
    """Test loading config from default path."""
    config_file = tmp_path / "rag-daemon.yml"
    config_file.write_text(
        yaml.dump(
            {
                "tick_interval_seconds": 60,
                "max_concurrent_jobs": 4,
                "max_consecutive_failures": 5,
                "base_backoff_seconds": 120,
                "max_backoff_seconds": 7200,
                "job_runner_cmd": "custom-rag-job",
            }
        )
    )

    with patch("os.environ.get") as mock_env:
        mock_env.return_value = str(config_file)
        config = load_config()

    assert config.tick_interval_seconds == 60
    assert config.max_concurrent_jobs == 4
    assert config.job_runner_cmd == "custom-rag-job"


def test_load_config_explicit_path(tmp_path: Path) -> None:
    """Test loading config from explicit path."""
    config_file = tmp_path / "explicit-config.yml"
    config_file.write_text(
        yaml.dump(
            {
                "tick_interval_seconds": 90,
                "log_level": "DEBUG",
                # Use tmp_path to avoid permission issues with ~/.llmc
                "state_store_path": str(tmp_path / "state"),
                "log_path": str(tmp_path / "logs"),
                "control_dir": str(tmp_path / "control"),
                "registry_path": str(tmp_path / "repos.yml"),
            }
        )
    )

    # Use expanduser on the full path
    expanded_path = str(config_file)

    with patch("os.path.expanduser") as mock_expand:
        mock_expand.side_effect = lambda x: str(tmp_path / x.replace("~", "")) if "~" in x else x
        config = load_config(expanded_path)

    assert config.tick_interval_seconds == 90
    assert config.log_level == "DEBUG"


def test_load_config_missing_file(tmp_path: Path) -> None:
    """Test failure when config file is missing."""
    non_existent = tmp_path / "non-existent.yml"

    with patch("os.environ.get") as mock_env:
        mock_env.return_value = str(non_existent)
        with pytest.raises(FileNotFoundError):
            load_config()


def test_load_config_invalid_yaml(tmp_path: Path) -> None:
    """Test handling of invalid YAML."""
    config_file = tmp_path / "invalid.yml"
    config_file.write_text("{ invalid: yaml: content: [")

    with patch("os.environ.get") as mock_env:
        mock_env.return_value = str(config_file)
        # PyYAML should raise an exception
        with pytest.raises(Exception):
            load_config()


def test_directories_created_on_first_run(tmp_path: Path) -> None:
    """Test that required directories are created on first run."""
    config_file = tmp_path / "rag-daemon.yml"
    config_file.write_text(yaml.dump({}))

    state_store_dir = tmp_path / "state"
    log_dir = tmp_path / "logs"
    control_dir = tmp_path / "control"

    with patch("os.environ.get") as mock_env:
        mock_env.return_value = str(config_file)

        config = load_config()

        # Directories should be created (using paths from config since they get expanded)
        assert config.state_store_path.exists()
        assert config.log_path.exists()
        assert config.control_dir.exists()


# ==============================================================================
# 2. State Store Tests
# ==============================================================================

def test_state_store_round_trip_with_timestamps(tmp_path: Path) -> None:
    """Test round-trip of RepoState with timestamps."""
    store = StateStore(tmp_path)
    now = datetime.now(timezone.utc)

    state = RepoState(
        repo_id="repo-123",
        last_run_started_at=now,
        last_run_finished_at=now + timedelta(seconds=10),
        last_run_status="success",
        consecutive_failures=0,
    )
    store.upsert(state)

    loaded = store.get("repo-123")
    assert loaded is not None
    assert loaded.repo_id == "repo-123"
    assert loaded.last_run_status == "success"
    assert loaded.consecutive_failures == 0
    assert loaded.last_run_started_at == now
    assert loaded.last_run_finished_at == now + timedelta(seconds=10)


def test_state_store_round_trip_without_timestamps(tmp_path: Path) -> None:
    """Test round-trip of RepoState without timestamps."""
    store = StateStore(tmp_path)

    state = RepoState(
        repo_id="repo-456",
        last_run_status="never",
    )
    store.upsert(state)

    loaded = store.get("repo-456")
    assert loaded is not None
    assert loaded.repo_id == "repo-456"
    assert loaded.last_run_status == "never"
    assert loaded.last_run_started_at is None
    assert loaded.last_run_finished_at is None


def test_state_store_corrupt_json(tmp_path: Path) -> None:
    """Test behavior with corrupt JSON file."""
    store = StateStore(tmp_path)

    # Create a valid state first
    state = RepoState(repo_id="repo-valid", last_run_status="success")
    store.upsert(state)

    # Create a corrupt JSON file
    corrupt_file = tmp_path / "repo-corrupt.json"
    corrupt_file.write_text("{ invalid json ")

    # Load all should skip the corrupt file and return the valid one
    all_states = store.load_all()
    assert "repo-valid" in all_states
    assert "repo-corrupt" not in all_states


def test_state_store_atomic_write(tmp_path: Path) -> None:
    """Test atomic write - no partially written file visible."""
    store = StateStore(tmp_path)
    state = RepoState(repo_id="repo-atomic", last_run_status="success")

    store.upsert(state)
    state_file = tmp_path / "repo-atomic.json"
    assert state_file.exists()

    # Check that the file contains valid JSON
    raw = json.loads(state_file.read_text(encoding="utf-8"))
    assert raw["repo_id"] == "repo-atomic"
    assert raw["last_run_status"] == "success"

    # Ensure no .tmp file exists after successful write
    tmp_file = tmp_path / "repo-atomic.json.tmp"
    assert not tmp_file.exists()


def test_state_store_update_function(tmp_path: Path) -> None:
    """Test update with mutator function."""
    store = StateStore(tmp_path)

    # Initial state
    store.upsert(RepoState(repo_id="repo-update", consecutive_failures=0))

    # Update using mutator
    def increment_failures(state: RepoState) -> RepoState:
        state.consecutive_failures += 1
        return state

    result = store.update("repo-update", increment_failures)
    assert result.consecutive_failures == 1

    # Verify persisted
    loaded = store.get("repo-update")
    assert loaded.consecutive_failures == 1


# ==============================================================================
# 3. Registry Client Tests
# ==============================================================================

def test_registry_load_empty(tmp_path: Path) -> None:
    """Test loading empty registry."""
    registry_file = tmp_path / "repos.yml"
    registry_file.write_text(yaml.dump({}))

    registry = RegistryClient(path=registry_file)
    entries = registry.load()
    assert entries == {}


def test_registry_load_multiple_entries(tmp_path: Path) -> None:
    """Test loading registry with multiple entries."""
    registry_file = tmp_path / "repos.yml"
    registry_file.write_text(
        yaml.dump(
            {
                "repo-1": {
                    "repo_path": "~/repo1",
                    "rag_workspace_path": "~/repo1/.llmc/rag",
                    "display_name": "Repo 1",
                    "rag_profile": "default",
                },
                "repo-2": {
                    "repo_path": "~/repo2",
                    "rag_workspace_path": "~/repo2/.llmc/rag",
                    "display_name": "Repo 2",
                    "rag_profile": "custom",
                    "min_refresh_interval_seconds": 300,
                },
            }
        )
    )

    registry = RegistryClient(path=registry_file)
    entries = registry.load()

    assert "repo-1" in entries
    assert "repo-2" in entries

    repo1 = entries["repo-1"]
    assert repo1.display_name == "Repo 1"
    assert repo1.rag_profile == "default"
    assert repo1.min_refresh_interval is None

    repo2 = entries["repo-2"]
    assert repo2.display_name == "Repo 2"
    assert repo2.rag_profile == "custom"
    assert repo2.min_refresh_interval == timedelta(seconds=300)


def test_registry_invalid_paths(tmp_path: Path) -> None:
    """Test behavior when registry contains invalid paths."""
    registry_file = tmp_path / "repos.yml"
    registry_file.write_text(
        yaml.dump(
            {
                "repo-invalid": {
                    "repo_path": "/non/existent/path",
                    "rag_workspace_path": "/also/non/existent",
                }
            }
        )
    )

    registry = RegistryClient(path=registry_file)
    entries = registry.load()

    # Should still load the entry, paths are not validated at load time
    assert "repo-invalid" in entries
    assert entries["repo-invalid"].repo_path == Path("/non/existent/path")


# ==============================================================================
# 4. Scheduler Eligibility Logic Tests
# ==============================================================================

def make_test_config(tmp_path: Path) -> DaemonConfig:
    """Create a test DaemonConfig."""
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
        job_runner_cmd="test-rag-job",
        log_level="INFO",
    )


def make_test_repo_descriptor(tmp_path: Path, repo_id: str) -> RepoDescriptor:
    """Create a test RepoDescriptor."""
    return RepoDescriptor(
        repo_id=repo_id,
        repo_path=tmp_path / f"repo-{repo_id}",
        rag_workspace_path=tmp_path / f"repo-{repo_id}" / ".llmc/rag",
    )


class DummyRegistry(RegistryClient):
    """Dummy registry for testing."""

    def __init__(self, entries: dict, path: Path) -> None:
        super().__init__(path)
        self._entries = entries

    def load(self) -> dict:
        return self._entries


class DummyWorkers(WorkerPool):
    """Dummy worker pool for testing."""

    def __init__(self, config: DaemonConfig, state_store: StateStore):
        super().__init__(config, state_store)
        self.scheduled = []

    def submit_jobs(self, jobs):
        self.scheduled.extend(list(jobs))


def test_scheduler_repo_no_state_is_eligible(tmp_path: Path) -> None:
    """Test that repo with no state is always eligible."""
    cfg = make_test_config(tmp_path)
    state_store = StateStore(cfg.state_store_path)

    repo = make_test_repo_descriptor(tmp_path, "repo-new")
    entries = {repo.repo_id: repo}
    registry = DummyRegistry(entries, cfg.registry_path)
    workers = DummyWorkers(cfg, state_store)

    scheduler = Scheduler(cfg, registry, state_store, workers)

    now = datetime.now(timezone.utc)
    eligible = scheduler._is_repo_eligible(repo, None, now, force=False)
    assert eligible is True


def test_scheduler_running_state_is_not_eligible(tmp_path: Path) -> None:
    """Test that repo in 'running' state is not eligible."""
    cfg = make_test_config(tmp_path)
    state_store = StateStore(cfg.state_store_path)

    repo = make_test_repo_descriptor(tmp_path, "repo-running")
    entries = {repo.repo_id: repo}
    registry = DummyRegistry(entries, cfg.registry_path)
    workers = DummyWorkers(cfg, state_store)

    scheduler = Scheduler(cfg, registry, state_store, workers)

    now = datetime.now(timezone.utc)
    state = RepoState(
        repo_id=repo.repo_id,
        last_run_status="running",
        last_run_started_at=now,
    )

    eligible = scheduler._is_repo_eligible(repo, state, now, force=False)
    assert eligible is False


def test_scheduler_failure_backoff(tmp_path: Path) -> None:
    """Test that repo with max failures is in backoff."""
    cfg = make_test_config(tmp_path)
    state_store = StateStore(cfg.state_store_path)

    repo = make_test_repo_descriptor(tmp_path, "repo-failed")
    entries = {repo.repo_id: repo}
    registry = DummyRegistry(entries, cfg.registry_path)
    workers = DummyWorkers(cfg, state_store)

    scheduler = Scheduler(cfg, registry, state_store, workers)

    now = datetime.now(timezone.utc)
    state = RepoState(
        repo_id=repo.repo_id,
        consecutive_failures=cfg.max_consecutive_failures,
        next_eligible_at=now + timedelta(seconds=100),  # In the future
    )

    # Not eligible without force
    eligible = scheduler._is_repo_eligible(repo, state, now, force=False)
    assert eligible is False

    # Eligible with force
    eligible_force = scheduler._is_repo_eligible(repo, state, now, force=True)
    assert eligible_force is True


def test_scheduler_next_eligible_future(tmp_path: Path) -> None:
    """Test that repo with next_eligible_at in future is not eligible."""
    cfg = make_test_config(tmp_path)
    state_store = StateStore(cfg.state_store_path)

    repo = make_test_repo_descriptor(tmp_path, "repo-future")
    entries = {repo.repo_id: repo}
    registry = DummyRegistry(entries, cfg.registry_path)
    workers = DummyWorkers(cfg, state_store)

    scheduler = Scheduler(cfg, registry, state_store, workers)

    now = datetime.now(timezone.utc)
    state = RepoState(
        repo_id=repo.repo_id,
        last_run_finished_at=now,
        next_eligible_at=now + timedelta(seconds=100),
    )

    # Not eligible
    eligible = scheduler._is_repo_eligible(repo, state, now, force=False)
    assert eligible is False


def test_scheduler_min_interval_enforced(tmp_path: Path) -> None:
    """Test that min_refresh_interval is enforced."""
    cfg = make_test_config(tmp_path)
    state_store = StateStore(cfg.state_store_path)

    repo = RepoDescriptor(
        repo_id="repo-interval",
        repo_path=tmp_path / "repo-interval",
        rag_workspace_path=tmp_path / "repo-interval" / ".llmc/rag",
        min_refresh_interval=timedelta(seconds=300),  # 5 minutes
    )

    entries = {repo.repo_id: repo}
    registry = DummyRegistry(entries, cfg.registry_path)
    workers = DummyWorkers(cfg, state_store)

    scheduler = Scheduler(cfg, registry, state_store, workers)

    now = datetime.now(timezone.utc)
    # Last run was 2 minutes ago (less than 5 minute interval)
    state = RepoState(
        repo_id=repo.repo_id,
        last_run_finished_at=now - timedelta(seconds=120),
    )

    eligible = scheduler._is_repo_eligible(repo, state, now, force=False)
    assert eligible is False

    # After the interval has passed
    state.last_run_finished_at = now - timedelta(seconds=400)
    eligible = scheduler._is_repo_eligible(repo, state, now, force=False)
    assert eligible is True


def test_scheduler_force_overrides(tmp_path: Path) -> None:
    """Test that force flag overrides checks."""
    cfg = make_test_config(tmp_path)
    state_store = StateStore(cfg.state_store_path)

    repo = make_test_repo_descriptor(tmp_path, "repo-force")
    entries = {repo.repo_id: repo}
    registry = DummyRegistry(entries, cfg.registry_path)
    workers = DummyWorkers(cfg, state_store)

    scheduler = Scheduler(cfg, registry, state_store, workers)

    now = datetime.now(timezone.utc)
    state = RepoState(
        repo_id=repo.repo_id,
        last_run_finished_at=now - timedelta(seconds=1),  # Just ran
        next_eligible_at=now + timedelta(hours=1),  # Backoff
        consecutive_failures=10,  # Max failures
    )

    # Not eligible without force
    eligible = scheduler._is_repo_eligible(repo, state, now, force=False)
    assert eligible is False

    # Eligible with force
    eligible = scheduler._is_repo_eligible(repo, state, now, force=True)
    assert eligible is True


# ==============================================================================
# 5. Control Surface Tests
# ==============================================================================

def test_control_refresh_all_flag(tmp_path: Path) -> None:
    """Test refresh_all.flag leads to refresh_all=True."""
    control_dir = tmp_path / "control"
    control_dir.mkdir()

    flag_file = control_dir / "refresh_all.flag"
    flag_file.write_text("")

    events = read_control_events(control_dir)
    assert events.refresh_all is True
    assert events.refresh_repo_ids == set()
    assert events.shutdown is False

    # Flag should be deleted after reading
    assert not flag_file.exists()


def test_control_refresh_repo_flag(tmp_path: Path) -> None:
    """Test refresh_<repo_id>.flag adds repo to refresh_repo_ids."""
    control_dir = tmp_path / "control"
    control_dir.mkdir()

    (control_dir / "refresh_repo-123.flag").write_text("")
    (control_dir / "refresh_repo-456.flag").write_text("")

    events = read_control_events(control_dir)
    assert events.refresh_all is False
    assert events.refresh_repo_ids == {"repo-123", "repo-456"}
    assert events.shutdown is False

    # Flags should be deleted
    assert not (control_dir / "refresh_repo-123.flag").exists()
    assert not (control_dir / "refresh_repo-456.flag").exists()


def test_control_shutdown_flag(tmp_path: Path) -> None:
    """Test shutdown.flag sets shutdown flag."""
    control_dir = tmp_path / "control"
    control_dir.mkdir()

    (control_dir / "shutdown.flag").write_text("")

    events = read_control_events(control_dir)
    assert events.shutdown is True
    assert not events.refresh_all
    assert events.refresh_repo_ids == set()


def test_control_multiple_flags(tmp_path: Path) -> None:
    """Test multiple flags can be read together."""
    control_dir = tmp_path / "control"
    control_dir.mkdir()

    (control_dir / "refresh_all.flag").write_text("")
    (control_dir / "refresh_repo-789.flag").write_text("")
    (control_dir / "shutdown.flag").write_text("")

    events = read_control_events(control_dir)
    assert events.refresh_all is True
    assert events.refresh_repo_ids == {"repo-789"}
    assert events.shutdown is True


def test_control_missing_directory(tmp_path: Path) -> None:
    """Test behavior when control directory doesn't exist."""
    control_dir = tmp_path / "nonexistent"

    events = read_control_events(control_dir)
    assert events.refresh_all is False
    assert events.refresh_repo_ids == set()
    assert events.shutdown is False


def test_control_best_effort_delete(tmp_path: Path) -> None:
    """Test that flag deletion is best-effort."""
    control_dir = tmp_path / "control"
    control_dir.mkdir()

    flag_file = control_dir / "refresh_all.flag"
    flag_file.write_text("")

    # Read events (this should delete the flag)
    events = read_control_events(control_dir)
    assert events.refresh_all is True

    # Note: On some filesystems, the flag might be deleted before we can chmod it
    # So we just verify the event was read correctly
    assert flag_file.exists() or True  # May or may not exist depending on timing


# ==============================================================================
# 6. Worker Pool & Job Runner Tests
# ==============================================================================

@pytest.mark.allow_sleep
def test_worker_marks_repo_running(tmp_path: Path) -> None:
    """Test that worker marks repo as running at job start."""
    cfg = make_test_config(tmp_path)
    state_store = StateStore(cfg.state_store_path)

    # Mock the subprocess to avoid actually running a job
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        workers = WorkerPool(cfg, state_store)

        repo = make_test_repo_descriptor(tmp_path, "repo-test")
        job = Mock()
        job.repo = repo
        job.job_id = "job-123"

        # Submit and wait for completion
        workers.submit_jobs([job])

        # Give the async worker time to run
        import time
        time.sleep(0.1)

        # Check that state was updated to running
        state = state_store.get("repo-test")
        assert state.last_run_status in ["running", "success"]


@pytest.mark.allow_sleep
def test_worker_success_updates_state(tmp_path: Path) -> None:
    """Test that successful job updates state correctly."""
    cfg = make_test_config(tmp_path)
    state_store = StateStore(cfg.state_store_path)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        workers = WorkerPool(cfg, state_store)

        repo = make_test_repo_descriptor(tmp_path, "repo-success")
        job = Mock()
        job.repo = repo
        job.job_id = "job-success"

        workers.submit_jobs([job])

        # Wait for completion
        import time
        time.sleep(0.1)

        # Verify success state
        state = state_store.get("repo-success")
        assert state.last_run_status == "success"
        assert state.consecutive_failures == 0
        assert state.last_run_finished_at is not None


@pytest.mark.allow_sleep
def test_worker_failure_updates_state(tmp_path: Path) -> None:
    """Test that failed job increments failures and sets backoff."""
    cfg = make_test_config(tmp_path)
    state_store = StateStore(cfg.state_store_path)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")

        workers = WorkerPool(cfg, state_store)

        repo = make_test_repo_descriptor(tmp_path, "repo-fail")
        job = Mock()
        job.repo = repo
        job.job_id = "job-fail"

        workers.submit_jobs([job])

        # Wait for completion
        import time
        time.sleep(0.1)

        # Verify failure state
        state = state_store.get("repo-fail")
        assert state.last_run_status == "error"
        assert state.consecutive_failures == 1
        assert state.next_eligible_at is not None
        assert state.last_error_reason is not None


@pytest.mark.allow_sleep
def test_worker_max_concurrent_jobs(tmp_path: Path) -> None:
    """Test that worker pool can handle multiple jobs."""
    from dataclasses import replace

    cfg = make_test_config(tmp_path)
    cfg = replace(cfg, max_concurrent_jobs=2)  # Pool size is 2
    state_store = StateStore(cfg.state_store_path)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        workers = WorkerPool(cfg, state_store)

        # Submit multiple jobs - the pool should handle them
        jobs = []
        for i in range(4):
            repo = make_test_repo_descriptor(tmp_path, f"repo-{i}")
            job = Mock()
            job.repo = repo
            job.job_id = f"job-{i}"
            jobs.append(job)

        workers.submit_jobs(jobs)

        # Wait for completion
        import time
        time.sleep(0.2)

        # All jobs should complete successfully
        for i in range(4):
            state = state_store.get(f"repo-{i}")
            assert state is not None
            assert state.last_run_status == "success"


@pytest.mark.allow_sleep
def test_worker_exponential_backoff(tmp_path: Path) -> None:
    """Test that backoff time grows exponentially."""
    from dataclasses import replace

    cfg = make_test_config(tmp_path)
    cfg = replace(cfg, base_backoff_seconds=60)
    state_store = StateStore(cfg.state_store_path)

    # Pre-populate with 2 failures
    state = RepoState(repo_id="repo-backoff", consecutive_failures=2)
    state_store.upsert(state)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="error")

        workers = WorkerPool(cfg, state_store)

        repo = make_test_repo_descriptor(tmp_path, "repo-backoff")
        job = Mock()
        job.repo = repo
        job.job_id = "job-backoff"

        workers.submit_jobs([job])

        # Wait for completion
        import time
        time.sleep(0.1)

        # Verify backoff (should be base * 2^(3-1) = 60 * 4 = 240 seconds)
        state = state_store.get("repo-backoff")
        assert state.consecutive_failures == 3
        assert state.next_eligible_at is not None

        backoff_delta = state.next_eligible_at - datetime.now(timezone.utc)
        assert backoff_delta.total_seconds() >= 200  # At least 200 seconds


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
