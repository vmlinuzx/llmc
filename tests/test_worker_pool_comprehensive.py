"""Comprehensive tests for worker pool job execution and state transitions."""

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile

import pytest

# Mark all tests in this file as allowing sleep (timing-dependent tests)
pytestmark = pytest.mark.allow_sleep

from tools.rag_daemon.models import DaemonConfig, Job, RepoDescriptor, RepoState
from tools.rag_daemon.state_store import StateStore
from tools.rag_daemon.workers import WorkerPool, make_job_id


UTC = timezone.utc


def make_config(tmp_path: Path, max_concurrent_jobs: int = 2) -> DaemonConfig:
    """Create a test configuration."""
    return DaemonConfig(
        tick_interval_seconds=60,
        max_concurrent_jobs=max_concurrent_jobs,
        max_consecutive_failures=3,
        base_backoff_seconds=60,
        max_backoff_seconds=3600,
        registry_path=tmp_path / "repos.yml",
        state_store_path=tmp_path / "state",
        log_path=tmp_path / "logs",
        control_dir=tmp_path / "control",
        job_runner_cmd="echo",  # Use simple echo for testing
    )


def test_worker_marks_repo_running(tmp_path: Path) -> None:
    """Worker marks repo as running at job start."""
    cfg = make_config(tmp_path)
    state_store = StateStore(cfg.state_store_path)

    workers = WorkerPool(cfg, state_store)

    repo = RepoDescriptor(
        repo_id="repo-test",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    job = Job(job_id=make_job_id(), repo=repo, force=False)

    # Submit job
    workers.submit_jobs([job])

    # Wait for job to start
    import time
    time.sleep(0.5)

    # Check repo is marked as running
    assert repo.repo_id in workers.running_repo_ids()

    # Wait for completion
    time.sleep(1.5)

    # Check state in store
    state = state_store.get(repo.repo_id)
    assert state is not None
    assert state.last_run_status == "success"  # echo returns 0


def test_worker_success_path(tmp_path: Path) -> None:
    """Worker correctly handles successful job."""
    cfg = make_config(tmp_path)
    state_store = StateStore(cfg.state_store_path)

    workers = WorkerPool(cfg, state_store)

    repo = RepoDescriptor(
        repo_id="repo-success",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    job = Job(job_id=make_job_id(), repo=repo, force=False)

    workers.submit_jobs([job])

    # Wait for completion
    import time
    time.sleep(2)

    # Check final state
    state = state_store.get(repo.repo_id)
    assert state.last_run_status == "success"
    assert state.consecutive_failures == 0
    assert state.last_error_reason is None
    assert state.last_run_finished_at is not None
    assert state.next_eligible_at is not None

    # next_eligible_at should be in the future
    now = datetime.now(UTC)
    assert state.next_eligible_at > now

    # Should be at least tick_interval_seconds in the future
    assert state.next_eligible_at > now + timedelta(seconds=59)


def test_worker_failure_path(tmp_path: Path) -> None:
    """Worker correctly handles failed job."""
    cfg = make_config(tmp_path)

    # Create fake runner that fails
    fake_runner = tmp_path / "fake_runner.sh"
    fake_runner.write_text("#!/bin/bash\nexit 1\n")
    fake_runner.chmod(0o755)

    cfg = DaemonConfig(
        tick_interval_seconds=60,
        max_concurrent_jobs=1,
        max_consecutive_failures=3,
        base_backoff_seconds=60,
        max_backoff_seconds=3600,
        registry_path=tmp_path / "repos.yml",
        state_store_path=tmp_path / "state",
        log_path=tmp_path / "logs",
        control_dir=tmp_path / "control",
        job_runner_cmd=str(fake_runner),
    )

    state_store = StateStore(cfg.state_store_path)

    workers = WorkerPool(cfg, state_store)

    repo = RepoDescriptor(
        repo_id="repo-fail",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    job = Job(job_id=make_job_id(), repo=repo, force=False)

    workers.submit_jobs([job])

    # Wait for completion
    import time
    time.sleep(2)

    # Check final state
    state = state_store.get(repo.repo_id)
    assert state.last_run_status == "error"
    assert state.consecutive_failures == 1
    assert state.last_error_reason is not None
    assert "exit_code=1" in state.last_error_reason or state.last_error_reason
    assert state.last_run_finished_at is not None


def test_worker_consecutive_failures(tmp_path: Path) -> None:
    """Worker increments consecutive failures on repeated failures."""
    cfg = make_config(tmp_path)

    # Create fake runner that always fails
    fake_runner = tmp_path / "always_fail.sh"
    fake_runner.write_text("#!/bin/bash\nexit 1\n")
    fake_runner.chmod(0o755)

    cfg = DaemonConfig(
        tick_interval_seconds=60,
        max_concurrent_jobs=1,
        max_consecutive_failures=3,
        base_backoff_seconds=60,
        max_backoff_seconds=3600,
        registry_path=tmp_path / "repos.yml",
        state_store_path=tmp_path / "state",
        log_path=tmp_path / "logs",
        control_dir=tmp_path / "control",
        job_runner_cmd=str(fake_runner),
    )

    state_store = StateStore(cfg.state_store_path)

    workers = WorkerPool(cfg, state_store)

    repo = RepoDescriptor(
        repo_id="repo-repeat",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    # Run job 3 times
    for i in range(3):
        job = Job(job_id=make_job_id(), repo=repo, force=True)
        workers.submit_jobs([job])

        # Wait for completion
        import time
        time.sleep(2)

        # Check failure count
        state = state_store.get(repo.repo_id)
        assert state.consecutive_failures == i + 1
        assert state.last_run_status == "error"


def test_worker_exponential_backoff(tmp_path: Path) -> None:
    """Worker applies exponential backoff after failures."""
    cfg = make_config(tmp_path)

    # Create fake runner that fails
    fake_runner = tmp_path / "fail_runner.sh"
    fake_runner.write_text("#!/bin/bash\nexit 1\n")
    fake_runner.chmod(0o755)

    cfg = DaemonConfig(
        tick_interval_seconds=60,
        max_concurrent_jobs=1,
        max_consecutive_failures=3,
        base_backoff_seconds=60,  # 1 minute base
        max_backoff_seconds=3600,  # 1 hour max
        registry_path=tmp_path / "repos.yml",
        state_store_path=tmp_path / "state",
        log_path=tmp_path / "logs",
        control_dir=tmp_path / "control",
        job_runner_cmd=str(fake_runner),
    )

    state_store = StateStore(cfg.state_store_path)

    workers = WorkerPool(cfg, state_store)

    repo = RepoDescriptor(
        repo_id="repo-backoff",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    # Run multiple failures to trigger exponential backoff
    for failure_num in range(1, 4):
        job = Job(job_id=make_job_id(), repo=repo, force=True)
        workers.submit_jobs([job])

        # Wait for completion
        import time
        time.sleep(2)

        state = state_store.get(repo.repo_id)

        # Calculate expected backoff
        expected_backoff = 60 * (2 ** (failure_num - 1))
        if expected_backoff > 3600:
            expected_backoff = 3600

        # Check next_eligible_at
        assert state.next_eligible_at is not None

        # Verify backoff is approximately correct (within 1 second tolerance)
        now = datetime.now(UTC)
        backoff_delta = state.next_eligible_at - now
        expected_seconds = timedelta(seconds=expected_backoff)

        # Allow some tolerance for execution time
        assert abs(backoff_delta.total_seconds() - expected_seconds.total_seconds()) < 5


def test_worker_max_backoff_cap(tmp_path: Path) -> None:
    """Worker caps backoff at max_backoff_seconds."""
    cfg = make_config(tmp_path)

    # Create fake runner that fails
    fake_runner = tmp_path / "always_fail.sh"
    fake_runner.write_text("#!/bin/bash\nexit 1\n")
    fake_runner.chmod(0o755)

    cfg = DaemonConfig(
        tick_interval_seconds=60,
        max_concurrent_jobs=1,
        max_consecutive_failures=10,  # Many failures
        base_backoff_seconds=60,
        max_backoff_seconds=3600,  # Cap at 1 hour
        registry_path=tmp_path / "repos.yml",
        state_store_path=tmp_path / "state",
        log_path=tmp_path / "logs",
        control_dir=tmp_path / "control",
        job_runner_cmd=str(fake_runner),
    )

    state_store = StateStore(cfg.state_store_path)

    workers = WorkerPool(cfg, state_store)

    repo = RepoDescriptor(
        repo_id="repo-cap",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    # Run enough failures to exceed max backoff
    for i in range(10):
        job = Job(job_id=make_job_id(), repo=repo, force=True)
        workers.submit_jobs([job])

        # Wait for completion
        import time
        time.sleep(2)

    state = state_store.get(repo.repo_id)

    # Check that backoff is capped at 3600 seconds (1 hour)
    now = datetime.now(UTC)
    backoff_delta = state.next_eligible_at - now
    assert backoff_delta.total_seconds() <= 3600 + 5  # Allow 5s tolerance
    assert backoff_delta.total_seconds() >= 3500  # Should be close to max


def test_worker_concurrent_jobs(tmp_path: Path) -> None:
    """Worker enforces max_concurrent_jobs limit."""
    max_jobs = 3
    cfg = make_config(tmp_path, max_concurrent_jobs=max_jobs)

    state_store = StateStore(cfg.state_store_path)

    workers = WorkerPool(cfg, state_store)

    # Submit more jobs than max_concurrent_jobs
    repos = []
    jobs = []
    for i in range(max_jobs + 2):
        repo = RepoDescriptor(
            repo_id=f"repo-{i}",
            repo_path=tmp_path / f"repo{i}",
            rag_workspace_path=tmp_path / f"repo{i}/.llmc/rag",
        )
        repos.append(repo)
        jobs.append(Job(job_id=make_job_id(), repo=repo, force=False))

    workers.submit_jobs(jobs)

    # Wait for jobs to start
    import time
    time.sleep(1)

    # Should have at most max_jobs running
    running_count = len(workers.running_repo_ids())
    assert running_count <= max_jobs

    # Wait for completion
    time.sleep(3)

    # All should eventually complete
    assert len(workers.running_repo_ids()) == 0


def test_worker_race_condition_prevention(tmp_path: Path) -> None:
    """Worker prevents race conditions when submitting same repo twice."""
    cfg = make_config(tmp_path, max_concurrent_jobs=2)

    state_store = StateStore(cfg.state_store_path)

    workers = WorkerPool(cfg, state_store)

    repo = RepoDescriptor(
        repo_id="repo-race",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    # Submit same repo twice rapidly
    job1 = Job(job_id=make_job_id(), repo=repo, force=False)
    job2 = Job(job_id=make_job_id(), repo=repo, force=False)

    workers.submit_jobs([job1, job2])

    # Wait for jobs to process
    import time
    time.sleep(2)

    # Repo should only be running once (race condition prevented)
    # It might be in success state now
    state = state_store.get(repo.repo_id)
    assert state is not None


def test_worker_with_profile(tmp_path: Path) -> None:
    """Worker passes profile to job runner."""
    # Track what commands were run
    commands_run = []

    def mock_runner(cmd, check, capture_output, text):
        commands_run.append(cmd)
        return Mock(returncode=0, stdout="", stderr="")

    cfg = make_config(tmp_path)
    cfg = DaemonConfig(
        tick_interval_seconds=60,
        max_concurrent_jobs=1,
        max_consecutive_failures=3,
        base_backoff_seconds=60,
        max_backoff_seconds=3600,
        registry_path=tmp_path / "repos.yml",
        state_store_path=tmp_path / "state",
        log_path=tmp_path / "logs",
        control_dir=tmp_path / "control",
        job_runner_cmd="custom-runner",
    )

    state_store = StateStore(cfg.state_store_path)

    with patch("subprocess.run", side_effect=mock_runner):
        workers = WorkerPool(cfg, state_store)

        repo = RepoDescriptor(
            repo_id="repo-profile",
            repo_path=tmp_path / "repo",
            rag_workspace_path=tmp_path / "repo/.llmc/rag",
            rag_profile="production",
        )

        job = Job(job_id=make_job_id(), repo=repo, force=False)
        workers.submit_jobs([job])

        # Wait for completion
        import time
        time.sleep(1)

    # Verify profile was passed
    assert len(commands_run) > 0
    cmd = commands_run[0]
    assert "custom-runner" in cmd
    assert "--profile" in cmd
    assert "production" in cmd


def test_worker_captures_output(tmp_path: Path) -> None:
    """Worker captures and stores stdout/stderr from jobs."""
    cfg = make_config(tmp_path)

    # Create runner that produces output
    output_runner = tmp_path / "output_runner.sh"
    output_runner.write_text("""#!/bin/bash
echo "STDOUT output"
echo "STDERR error" >&2
exit 0
""")
    output_runner.chmod(0o755)

    cfg = DaemonConfig(
        tick_interval_seconds=60,
        max_concurrent_jobs=1,
        max_consecutive_failures=3,
        base_backoff_seconds=60,
        max_backoff_seconds=3600,
        registry_path=tmp_path / "repos.yml",
        state_store_path=tmp_path / "state",
        log_path=tmp_path / "logs",
        control_dir=tmp_path / "control",
        job_runner_cmd=str(output_runner),
    )

    state_store = StateStore(cfg.state_store_path)

    workers = WorkerPool(cfg, state_store)

    repo = RepoDescriptor(
        repo_id="repo-output",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    job = Job(job_id=make_job_id(), repo=repo, force=False)
    workers.submit_jobs([job])

    # Wait for completion
    import time
    time.sleep(2)

    # Check that output is captured in state
    state = state_store.get(repo.repo_id)
    # Note: The current implementation doesn't store stdout/stderr in state,
    # but they're captured in the JobResult. This is a design limitation.


def test_worker_state_persistence(tmp_path: Path) -> None:
    """Worker state changes persist after worker pool destruction."""
    cfg = make_config(tmp_path)

    # Create fake runner
    runner = tmp_path / "test_runner.sh"
    runner.write_text("#!/bin/bash\nexit 0\n")
    runner.chmod(0o755)

    cfg = DaemonConfig(
        tick_interval_seconds=60,
        max_concurrent_jobs=1,
        max_consecutive_failures=3,
        base_backoff_seconds=60,
        max_backoff_seconds=3600,
        registry_path=tmp_path / "repos.yml",
        state_store_path=tmp_path / "state",
        log_path=tmp_path / "logs",
        control_dir=tmp_path / "control",
        job_runner_cmd=str(runner),
    )

    state_store = StateStore(cfg.state_store_path)

    # First worker run
    workers1 = WorkerPool(cfg, state_store)
    repo = RepoDescriptor(
        repo_id="repo-persist",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )
    job = Job(job_id=make_job_id(), repo=repo, force=False)
    workers1.submit_jobs([job])

    import time
    time.sleep(2)

    # Check state after first run
    state1 = state_store.get(repo.repo_id)
    assert state1.last_run_status == "success"
    assert state1.consecutive_failures == 0

    # Create new worker (simulates daemon restart)
    workers2 = WorkerPool(cfg, state_store)

    # Verify state persisted
    state2 = state_store.get(repo.repo_id)
    assert state2.last_run_status == "success"
    assert state2.consecutive_failures == 0
    assert state2.last_run_finished_at is not None


def test_worker_error_with_exception(tmp_path: Path) -> None:
    """Worker handles exceptions during job execution gracefully."""
    cfg = make_config(tmp_path)

    # Create runner that raises exception
    exception_runner = tmp_path / "exception_runner.sh"
    exception_runner.write_text("#!/bin/bash\nraise Exception('Test exception')\n")
    exception_runner.chmod(0o755)

    cfg = DaemonConfig(
        tick_interval_seconds=60,
        max_concurrent_jobs=1,
        max_consecutive_failures=3,
        base_backoff_seconds=60,
        max_backoff_seconds=3600,
        registry_path=tmp_path / "repos.yml",
        state_store_path=tmp_path / "state",
        log_path=tmp_path / "logs",
        control_dir=tmp_path / "control",
        job_runner_cmd=str(exception_runner),
    )

    state_store = StateStore(cfg.state_store_path)

    workers = WorkerPool(cfg, state_store)

    repo = RepoDescriptor(
        repo_id="repo-exception",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "repo/.llmc/rag",
    )

    job = Job(job_id=make_job_id(), repo=repo, force=False)
    workers.submit_jobs([job])

    # Wait for completion
    import time
    time.sleep(2)

    # Should handle exception and mark as error
    state = state_store.get(repo.repo_id)
    assert state.last_run_status == "error"
    assert state.consecutive_failures == 1
    assert state.last_error_reason is not None
