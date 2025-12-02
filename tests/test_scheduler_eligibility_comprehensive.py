"""Comprehensive tests for scheduler eligibility logic."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from tools.rag_daemon.models import (
    DaemonConfig,
    RepoDescriptor,
    RepoState,
)
from tools.rag_daemon.scheduler import Scheduler

UTC = UTC


class DummyRegistry:
    """Mock registry for testing."""

    def __init__(self, entries):
        self._entries = entries

    def load(self):
        return self._entries


class DummyWorkers:
    """Mock workers that track submitted jobs."""

    def __init__(self):
        self.submitted = []

    def submit_jobs(self, jobs):
        self.submitted.extend(jobs)

    def running_repo_ids(self):
        return set()


def make_config(tmp_path: Path) -> DaemonConfig:
    """Create a test configuration."""
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


def test_scheduler_eligibility_no_state(tmp_path: Path) -> None:
    """Repo with no state is always eligible."""
    cfg = make_config(tmp_path)
    repo = RepoDescriptor(
        repo_id="repo-new",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    registry = DummyRegistry({"repo-new": repo})
    workers = DummyWorkers()

    scheduler = Scheduler(cfg, registry, None, workers)

    # With no state, should be eligible
    assert scheduler._is_repo_eligible(repo, None, datetime.now(UTC), force=False) is True


def test_scheduler_eligibility_running_state(tmp_path: Path) -> None:
    """Repo in running state is not eligible."""
    cfg = make_config(tmp_path)
    repo = RepoDescriptor(
        repo_id="repo-running",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    registry = DummyRegistry({"repo-running": repo})
    workers = DummyWorkers()

    scheduler = Scheduler(cfg, registry, None, workers)

    # With running state, should NOT be eligible
    state = RepoState(repo_id="repo-running", last_run_status="running")
    assert scheduler._is_repo_eligible(repo, state, datetime.now(UTC), force=False) is False

    # Unless forced
    assert scheduler._is_repo_eligible(repo, state, datetime.now(UTC), force=True) is True


def test_scheduler_eligibility_consecutive_failures(tmp_path: Path) -> None:
    """Repo with max consecutive failures is not eligible."""
    cfg = make_config(tmp_path)
    repo = RepoDescriptor(
        repo_id="repo-failing",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    registry = DummyRegistry({"repo-failing": repo})
    workers = DummyWorkers()

    scheduler = Scheduler(cfg, registry, None, workers)

    # At max failures, should NOT be eligible
    state = RepoState(
        repo_id="repo-failing",
        last_run_status="error",
        consecutive_failures=3,  # max_consecutive_failures=3
    )
    assert scheduler._is_repo_eligible(repo, state, datetime.now(UTC), force=False) is False

    # But forced refresh should work
    assert scheduler._is_repo_eligible(repo, state, datetime.now(UTC), force=True) is True

    # One below max should be eligible
    state_below = RepoState(
        repo_id="repo-failing",
        last_run_status="error",
        consecutive_failures=2,
    )
    assert scheduler._is_repo_eligible(repo, state_below, datetime.now(UTC), force=False) is True


def test_scheduler_eligibility_next_eligible_in_future(tmp_path: Path) -> None:
    """Repo with next_eligible_at in future is not eligible."""
    cfg = make_config(tmp_path)
    repo = RepoDescriptor(
        repo_id="repo-cooldown",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    registry = DummyRegistry({"repo-cooldown": repo})
    workers = DummyWorkers()

    scheduler = Scheduler(cfg, registry, None, workers)

    now = datetime.now(UTC)
    future_time = now + timedelta(seconds=300)  # 5 minutes in future

    state = RepoState(
        repo_id="repo-cooldown",
        last_run_status="error",
        consecutive_failures=1,
        next_eligible_at=future_time,
    )

    # Not eligible when next_eligible_at is in future
    assert scheduler._is_repo_eligible(repo, state, now, force=False) is False

    # But forced should override
    assert scheduler._is_repo_eligible(repo, state, now, force=True) is True

    # When time has passed, should be eligible again
    past_time = now + timedelta(seconds=600)
    assert scheduler._is_repo_eligible(repo, state, past_time, force=False) is True


def test_scheduler_eligibility_min_refresh_interval(tmp_path: Path) -> None:
    """Repo that ran recently (within min interval) is not eligible."""
    cfg = make_config(tmp_path)
    repo = RepoDescriptor(
        repo_id="repo-recent",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    registry = DummyRegistry({"repo-recent": repo})
    workers = DummyWorkers()

    scheduler = Scheduler(cfg, registry, None, workers)

    now = datetime.now(UTC)
    recent_run = now - timedelta(seconds=30)  # Just ran 30 seconds ago

    state = RepoState(
        repo_id="repo-recent",
        last_run_status="success",
        last_run_finished_at=recent_run,
    )

    # Should NOT be eligible (tick interval is 60s, only 30s since last run)
    assert scheduler._is_repo_eligible(repo, state, now, force=False) is False

    # Forced should override
    assert scheduler._is_repo_eligible(repo, state, now, force=True) is True

    # After interval has passed, should be eligible
    later = now + timedelta(seconds=40)
    assert scheduler._is_repo_eligible(repo, state, later, force=False) is True


def test_scheduler_eligibility_with_custom_min_interval(tmp_path: Path) -> None:
    """Repo respects custom min_refresh_interval setting."""
    cfg = make_config(tmp_path)
    repo = RepoDescriptor(
        repo_id="repo-custom",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
        min_refresh_interval=timedelta(hours=2),  # Custom 2-hour interval
    )

    registry = DummyRegistry({"repo-custom": repo})
    workers = DummyWorkers()

    scheduler = Scheduler(cfg, registry, None, workers)

    now = datetime.now(UTC)
    recent_run = now - timedelta(minutes=30)  # 30 minutes ago

    state = RepoState(
        repo_id="repo-custom",
        last_run_status="success",
        last_run_finished_at=recent_run,
    )

    # Should NOT be eligible (custom interval is 2 hours, only 30 min passed)
    assert scheduler._is_repo_eligible(repo, state, now, force=False) is False

    # But forced should work
    assert scheduler._is_repo_eligible(repo, state, now, force=True) is True

    # After custom interval, should be eligible
    way_later = now + timedelta(hours=3)
    assert scheduler._is_repo_eligible(repo, state, way_later, force=False) is True


def test_scheduler_eligibility_success_state(tmp_path: Path) -> None:
    """Repo in success state is eligible only after interval."""
    cfg = make_config(tmp_path)
    repo = RepoDescriptor(
        repo_id="repo-success",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    registry = DummyRegistry({"repo-success": repo})
    workers = DummyWorkers()

    scheduler = Scheduler(cfg, registry, None, workers)

    now = datetime.now(UTC)
    old_run = now - timedelta(minutes=2)  # 2 minutes ago

    state = RepoState(
        repo_id="repo-success",
        last_run_status="success",
        last_run_finished_at=old_run,
    )

    # Should be eligible (tick interval 60s, 120s since last run)
    assert scheduler._is_repo_eligible(repo, state, now, force=False) is True


def test_scheduler_run_tick_with_mixed_states(tmp_path: Path) -> None:
    """Scheduler tick correctly filters repos based on eligibility."""
    cfg = make_config(tmp_path)

    # Create repos
    repo_new = RepoDescriptor(
        repo_id="repo-new",
        repo_path=tmp_path / "repo1",
        rag_workspace_path=tmp_path / "repo1/.llmc/rag",
    )
    repo_running = RepoDescriptor(
        repo_id="repo-running",
        repo_path=tmp_path / "repo2",
        rag_workspace_path=tmp_path / "repo2/.llmc/rag",
    )
    repo_failed = RepoDescriptor(
        repo_id="repo-failed",
        repo_path=tmp_path / "repo3",
        rag_workspace_path=tmp_path / "repo3/.llmc/rag",
    )
    repo_success = RepoDescriptor(
        repo_id="repo-success",
        repo_path=tmp_path / "repo4",
        rag_workspace_path=tmp_path / "repo4/.llmc/rag",
    )
    repo_cooldown = RepoDescriptor(
        repo_id="repo-cooldown",
        repo_path=tmp_path / "repo5",
        rag_workspace_path=tmp_path / "repo5/.llmc/rag",
    )

    registry = DummyRegistry(
        {
            "repo-new": repo_new,
            "repo-running": repo_running,
            "repo-failed": repo_failed,
            "repo-success": repo_success,
            "repo-cooldown": repo_cooldown,
        }
    )

    workers = DummyWorkers()

    scheduler = Scheduler(cfg, registry, None, workers)

    now = datetime.now(UTC)

    # Create states
    states = {
        "repo-running": RepoState(
            repo_id="repo-running", last_run_status="running"
        ),
        "repo-failed": RepoState(
            repo_id="repo-failed",
            last_run_status="error",
            consecutive_failures=3,  # Max failures
        ),
        "repo-success": RepoState(
            repo_id="repo-success",
            last_run_status="success",
            last_run_finished_at=now - timedelta(minutes=2),  # Old enough
        ),
        "repo-cooldown": RepoState(
            repo_id="repo-cooldown",
            last_run_status="error",
            next_eligible_at=now + timedelta(seconds=300),  # In future
        ),
    }

    # Mock the control and state store
    with patch("tools.rag_daemon.scheduler.read_control_events") as mock_control:
        mock_control.return_value = Mock(refresh_all=False, refresh_repo_ids=set(), shutdown=False)

        with patch.object(scheduler.state_store, "load_all", return_value=states):
            with patch.object(workers, "running_repo_ids", return_value=set()):
                scheduler._run_tick()

    # Should submit only repo-new (no state) and repo-success (success but old enough)
    submitted_ids = {job.repo.repo_id for job in workers.submitted}
    assert "repo-new" in submitted_ids
    assert "repo-success" in submitted_ids

    # Should NOT submit
    assert "repo-running" not in submitted_ids  # Running state
    assert "repo-failed" not in submitted_ids  # Max failures
    assert "repo-cooldown" not in submitted_ids  # In cooldown


def test_scheduler_run_tick_with_force_flags(tmp_path: Path) -> None:
    """Force flags override eligibility checks."""
    cfg = make_config(tmp_path)

    repo = RepoDescriptor(
        repo_id="repo-force",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    registry = DummyRegistry({"repo-force": repo})

    workers = DummyWorkers()

    scheduler = Scheduler(cfg, registry, None, workers)

    now = datetime.now(UTC)
    future_time = now + timedelta(seconds=300)

    states = {
        "repo-force": RepoState(
            repo_id="repo-force",
            last_run_status="error",
            consecutive_failures=3,  # Max failures
            next_eligible_at=future_time,
        )
    }

    # Test with refresh_all flag
    with patch("tools.rag_daemon.scheduler.read_control_events") as mock_control:
        mock_control.return_value = Mock(
            refresh_all=True, refresh_repo_ids=set(), shutdown=False
        )

        with patch.object(scheduler.state_store, "load_all", return_value=states):
            with patch.object(workers, "running_repo_ids", return_value=set()):
                workers.submitted = []
                scheduler._run_tick()

        # Should submit despite being ineligible
        assert len(workers.submitted) == 1
        assert workers.submitted[0].repo.repo_id == "repo-force"
        assert workers.submitted[0].force is True

    # Test with repo-specific flag
    with patch("tools.rag_daemon.scheduler.read_control_events") as mock_control:
        mock_control.return_value = Mock(
            refresh_all=False, refresh_repo_ids={"repo-force"}, shutdown=False
        )

        with patch.object(scheduler.state_store, "load_all", return_value=states):
            with patch.object(workers, "running_repo_ids", return_value=set()):
                workers.submitted = []
                scheduler._run_tick()

        # Should submit with force flag
        assert len(workers.submitted) == 1
        assert workers.submitted[0].force is True


def test_scheduler_eligibility_error_state(tmp_path: Path) -> None:
    """Repo in error state (but below max failures) is eligible."""
    cfg = make_config(tmp_path)
    repo = RepoDescriptor(
        repo_id="repo-error",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    registry = DummyRegistry({"repo-error": repo})
    workers = DummyWorkers()

    scheduler = Scheduler(cfg, registry, None, workers)

    state = RepoState(
        repo_id="repo-error",
        last_run_status="error",
        consecutive_failures=2,  # Below max of 3
    )

    # Should be eligible (below max failures, no next_eligible_at set)
    assert scheduler._is_repo_eligible(repo, state, datetime.now(UTC), force=False) is True


def test_scheduler_eligibility_skipped_state(tmp_path: Path) -> None:
    """Repo in skipped state is treated like success."""
    cfg = make_config(tmp_path)
    repo = RepoDescriptor(
        repo_id="repo-skipped",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    registry = DummyRegistry({"repo-skipped": repo})
    workers = DummyWorkers()

    scheduler = Scheduler(cfg, registry, None, workers)

    state = RepoState(
        repo_id="repo-skipped",
        last_run_status="skipped",
        last_run_finished_at=datetime.now(UTC) - timedelta(minutes=2),
    )

    # Should be eligible (skipped doesn't prevent re-eligibility)
    assert scheduler._is_repo_eligible(repo, state, datetime.now(UTC), force=False) is True
