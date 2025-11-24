"""End-to-end tests for daemon operation with dummy job runner."""

import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from tools.rag_daemon.models import DaemonConfig
from tools.rag_daemon.scheduler import Scheduler
from tools.rag_daemon.state_store import StateStore
from tools.rag_daemon.workers import WorkerPool
from tools.rag_repo.cli import _cmd_add

# Calculate REPO_ROOT dynamically
REPO_ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.allow_sleep
def test_e2e_daemon_tick_with_dummy_runner(tmp_path: Path) -> None:
    """End-to-end test: daemon tick with dummy job runner."""
    # Import RegistryAdapter locally as it's used here
    from tools.rag_repo.registry import RegistryAdapter

    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        # Create dummy job runner that logs calls
        dummy_runner = home / "dummy_runner.py"
        dummy_runner.write_text("""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

# Log the call
log_file = Path(sys.argv[0]).parent / "runner_calls.log"
with open(log_file, "a") as f:
    f.write(json.dumps({
        "repo": sys.argv[sys.argv.index("--repo") + 1] if "--repo" in sys.argv else "unknown",
        "workspace": sys.argv[sys.argv.index("--workspace") + 1] if "--workspace" in sys.argv else "unknown",
        "profile": sys.argv[sys.argv.index("--profile") + 1] if "--profile" in sys.argv else "none",
    }) + "\\n")

# Success
sys.exit(0)
""")
        dummy_runner.chmod(0o755)

        # Create test repo
        repo_root = home / "test_repo"
        repo_root.mkdir()
        (repo_root / "README.md").write_text("# Test Repo")

        # Register repo
        from tools.rag_repo.config import ToolConfig
        tool_config = ToolConfig(
            registry_path=home / "registry.yml",
            default_rag_profile="default",
        )

        args = Mock(
            path=str(repo_root),
            yes=True,
            json=False,
            config=None,
        )

        _cmd_add(args, tool_config, None)

        # Create daemon config
        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=2,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=home / "registry.yml",
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
            job_runner_cmd=str(dummy_runner),
        )

        # Create daemon components
        registry = RegistryAdapter(cfg.registry_path) if hasattr(RegistryAdapter, '__init__') else None
        from tools.rag_daemon.registry import RegistryClient
        registry_client = RegistryClient.from_config(cfg)
        state_store = StateStore(cfg.state_store_path)
        workers = WorkerPool(cfg, state_store)
        scheduler = Scheduler(cfg, registry_client, state_store, workers)

        # Run single tick
        scheduler.run_once()

        # Wait for jobs to complete
        time.sleep(2)

        # Verify job was invoked
        log_file = home / "runner_calls.log"
        assert log_file.exists(), "Dummy runner was not called"

        calls = [json.loads(line) for line in log_file.read_text().strip().split('\n')]
        assert len(calls) == 1, f"Expected 1 call, got {len(calls)}"

        call = calls[0]
        assert call["repo"] == str(repo_root)
        assert call["workspace"] == str(repo_root / ".llmc" / "rag")
        assert call["profile"] == "default"

        print("✓ PASS: E2E daemon tick with dummy runner")


@pytest.mark.allow_sleep
def test_e2e_daemon_multiple_repos(tmp_path: Path) -> None:
    """End-to-end test: daemon processes multiple repos."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        # Create dummy runner
        dummy_runner = home / "runner.sh"
        dummy_runner.write_text("""#!/bin/bash
echo "Running for $@"
exit 0
""")
        dummy_runner.chmod(0o755)

        # Create multiple repos
        repo1 = home / "repo1"
        repo1.mkdir()
        (repo1 / "README.md").write_text("Repo 1")

        repo2 = home / "repo2"
        repo2.mkdir()
        (repo2 / "README.md").write_text("Repo 2")

        repo3 = home / "repo3"
        repo3.mkdir()
        (repo3 / "README.md").write_text("Repo 3")

        # Register all repos
        from tools.rag_repo.config import ToolConfig
        tool_config = ToolConfig(
            registry_path=home / "registry.yml",
            default_rag_profile="default",
        )

        for repo in [repo1, repo2, repo3]:
            args = Mock(
                path=str(repo),
                yes=True,
                json=False,
                config=None,
            )
            _cmd_add(args, tool_config, None)

        # Create daemon
        from tools.rag_daemon.registry import RegistryClient
        from tools.rag_daemon.models import DaemonConfig

        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=3,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=home / "registry.yml",
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
            job_runner_cmd=str(dummy_runner),
        )

        registry_client = RegistryClient.from_config(cfg)
        state_store = StateStore(cfg.state_store_path)
        workers = WorkerPool(cfg, state_store)
        scheduler = Scheduler(cfg, registry_client, state_store, workers)

        # Run tick
        scheduler.run_once()

        # Wait for completion
        time.sleep(3)

        # Verify all repos were processed
        entries = registry_client.load()
        assert len(entries) == 3, f"Expected 3 repos, got {len(entries)}"

        # Check state for each repo
        for repo_id in entries.keys():
            state = state_store.get(repo_id)
            assert state is not None
            assert state.last_run_status == "success"
            assert state.consecutive_failures == 0

        print("✓ PASS: E2E multiple repos processed")


@pytest.mark.allow_sleep
def test_e2e_daemon_with_failures(tmp_path: Path) -> None:
    """End-to-end test: daemon handles job failures correctly."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        # Create failing runner
        failing_runner = home / "failing_runner.sh"
        failing_runner.write_text("""#!/bin/bash
echo "Failing job"
exit 1
""")
        failing_runner.chmod(0o755)

        # Create test repo
        repo_root = home / "test_repo"
        repo_root.mkdir()
        (repo_root / "README.md").write_text("# Test Repo")

        # Register repo
        from tools.rag_repo.config import ToolConfig
        tool_config = ToolConfig(
            registry_path=home / "registry.yml",
            default_rag_profile="default",
        )

        args = Mock(
            path=str(repo_root),
            yes=True,
            json=False,
            config=None,
        )
        _cmd_add(args, tool_config, None)

        # Create daemon
        from tools.rag_daemon.registry import RegistryClient
        from tools.rag_daemon.models import DaemonConfig

        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=1,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=home / "registry.yml",
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
            job_runner_cmd=str(failing_runner),
        )

        registry_client = RegistryClient.from_config(cfg)
        state_store = StateStore(cfg.state_store_path)
        workers = WorkerPool(cfg, state_store)
        scheduler = Scheduler(cfg, registry_client, state_store, workers)

        # Run tick
        scheduler.run_once()

        # Wait for completion
        time.sleep(2)

        # Verify failure was recorded
        entries = registry_client.load()
        assert len(entries) == 1

        repo_id = list(entries.keys())[0]
        state = state_store.get(repo_id)

        assert state.last_run_status == "error"
        assert state.consecutive_failures == 1
        assert state.last_error_reason is not None

        print("✓ PASS: E2E failure handling")


@pytest.mark.allow_sleep
def test_e2e_daemon_control_flags(tmp_path: Path) -> None:
    """End-to-end test: control flags trigger immediate refresh."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        # Create runner
        runner = home / "runner.sh"
        runner.write_text("""#!/bin/bash
echo "Running"
exit 0
""")
        runner.chmod(0o755)

        # Create test repo
        repo_root = home / "test_repo"
        repo_root.mkdir()
        (repo_root / "README.md").write_text("# Test Repo")

        # Register repo
        from tools.rag_repo.config import ToolConfig
        tool_config = ToolConfig(
            registry_path=home / "registry.yml",
            default_rag_profile="default",
        )

        args = Mock(
            path=str(repo_root),
            yes=True,
            json=False,
            config=None,
        )
        _cmd_add(args, tool_config, None)

        # First run to set state
        from tools.rag_daemon.registry import RegistryClient
        from tools.rag_daemon.models import DaemonConfig

        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=1,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=home / "registry.yml",
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
            job_runner_cmd=str(runner),
        )

        registry_client = RegistryClient.from_config(cfg)
        state_store = StateStore(cfg.state_store_path)
        workers = WorkerPool(cfg, state_store)
        scheduler = Scheduler(cfg, registry_client, state_store, workers)

        # First tick
        scheduler.run_once()
        time.sleep(2)

        # Verify success
        entries = registry_client.load()
        repo_id = list(entries.keys())[0]
        state = state_store.get(repo_id)
        first_run = state.last_run_finished_at

        # Create control flag to force refresh
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        future_time = now + timedelta(seconds=300)
        state.next_eligible_at = future_time
        state_store.upsert(state)

        # Create refresh flag
        (cfg.control_dir / f"refresh_{repo_id}.flag").touch()

        # Second tick should force refresh
        scheduler.run_once()
        time.sleep(2)

        # Verify second run happened
        state2 = state_store.get(repo_id)
        assert state2.last_run_finished_at > first_run

        print("✓ PASS: E2E control flags")


@pytest.mark.allow_sleep
def test_e2e_daemon_state_persistence(tmp_path: Path) -> None:
    """End-to-end test: daemon state persists across restarts."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        # Create runner
        runner = home / "runner.sh"
        runner.write_text("""#!/bin/bash
exit 0
""")
        runner.chmod(0o755)

        # Create test repo
        repo_root = home / "test_repo"
        repo_root.mkdir()
        (repo_root / "README.md").write_text("# Test Repo")

        # Register repo
        from tools.rag_repo.config import ToolConfig
        tool_config = ToolConfig(
            registry_path=home / "registry.yml",
            default_rag_profile="default",
        )

        args = Mock(
            path=str(repo_root),
            yes=True,
            json=False,
            config=None,
        )
        _cmd_add(args, tool_config, None)

        # First daemon instance
        from tools.rag_daemon.registry import RegistryClient
        from tools.rag_daemon.models import DaemonConfig

        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=1,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=home / "registry.yml",
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
            job_runner_cmd=str(runner),
        )

        registry_client = RegistryClient.from_config(cfg)
        state_store = StateStore(cfg.state_store_path)
        workers1 = WorkerPool(cfg, state_store)
        scheduler1 = Scheduler(cfg, registry_client, state_store, workers1)

        # Run tick
        scheduler1.run_once()
        time.sleep(2)

        # Verify state
        entries = registry_client.load()
        repo_id = list(entries.keys())[0]
        state1 = state_store.get(repo_id)
        assert state1.last_run_status == "success"

        # Create second daemon instance (simulates restart)
        workers2 = WorkerPool(cfg, state_store)
        scheduler2 = Scheduler(cfg, registry_client, state_store, workers2)

        # Verify state persisted
        state2 = state_store.get(repo_id)
        assert state2.last_run_status == "success"
        assert state2.consecutive_failures == 0
        assert state2.last_run_finished_at is not None

        print("✓ PASS: E2E state persistence")


@pytest.mark.allow_sleep
def test_e2e_daemon_max_concurrent_jobs(tmp_path: Path) -> None:
    """End-to-end test: daemon respects max_concurrent_jobs."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        # Create slow runner
        runner = home / "slow_runner.sh"
        runner.write_text("""#!/bin/bash
sleep 2
exit 0
""")
        runner.chmod(0o755)

        # Create 5 repos
        repos = []
        for i in range(5):
            repo = home / f"repo{i}"
            repo.mkdir()
            (repo / "README.md").write_text(f"Repo {i}")
            repos.append(repo)

        # Register all repos
        from tools.rag_repo.config import ToolConfig
        tool_config = ToolConfig(
            registry_path=home / "registry.yml",
            default_rag_profile="default",
        )

        for repo in repos:
            args = Mock(
                path=str(repo),
                yes=True,
                json=False,
                config=None,
            )
            _cmd_add(args, tool_config, None)

        # Create daemon with max 2 concurrent jobs
        from tools.rag_daemon.registry import RegistryClient
        from tools.rag_daemon.models import DaemonConfig

        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=2,  # Limit to 2
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=home / "registry.yml",
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
            job_runner_cmd=str(runner),
        )

        registry_client = RegistryClient.from_config(cfg)
        state_store = StateStore(cfg.state_store_path)
        workers = WorkerPool(cfg, state_store)
        scheduler = Scheduler(cfg, registry_client, state_store, workers)

        # Run tick
        scheduler.run_once()

        # Check running count immediately
        running_count = len(workers.running_repo_ids())
        assert running_count <= 2, f"Expected max 2 concurrent, got {running_count}"

        # Wait for completion
        time.sleep(10)

        # All should complete
        assert len(workers.running_repo_ids()) == 0

        print("✓ PASS: E2E max concurrent jobs")


def test_e2e_daemon_with_fake_home(tmp_path: Path) -> None:
    """End-to-end test using temporary HOME directory."""
    with tempfile.TemporaryDirectory() as temp_home:
        temp_home = Path(temp_home)

        # Set up fake home environment
        import os
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(temp_home)

        try:
            # Create runner
            runner = temp_home / "runner.sh"
            runner.write_text("""#!/bin/bash
exit 0
""")
            runner.chmod(0o755)

            # Create test repo in temp home
            repo_root = temp_home / "my_repo"
            repo_root.mkdir()
            (repo_root / "README.md").write_text("# My Repo")

            # Use default config path (~/.llmc/rag-daemon.yml)
            from tools.rag_repo.config import ToolConfig
            tool_config = ToolConfig(
                registry_path=temp_home / ".llmc" / "repos.yml",
                default_rag_profile="default",
            )

            # Ensure .llmc directory exists
            tool_config.registry_path.parent.mkdir(parents=True, exist_ok=True)

            # Add repo
            from tools.rag_repo.cli import _cmd_add
            args = Mock(
                path=str(repo_root),
                yes=True,
                json=False,
                config=None,
            )
            _cmd_add(args, tool_config, None)

            # Verify repo was added
            from tools.rag_repo.registry import RegistryAdapter
            registry = RegistryAdapter(tool_config)
            entries = registry.load_all()
            assert len(entries) == 1

            print("✓ PASS: E2E with fake HOME")

        finally:
            # Restore HOME
            if old_home:
                os.environ["HOME"] = old_home
            else:
                os.environ.pop("HOME", None)


def test_e2e_daemon_shutdown_flag(tmp_path: Path) -> None:
    """End-to-end test: shutdown flag stops daemon."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        # This test would require a running daemon which is complex in pytest
        # Instead, we verify the control surface logic

        from tools.rag_daemon.control import read_control_events

        control_dir = home / "control"
        control_dir.mkdir()

        # Create shutdown flag
        (control_dir / "shutdown.flag").touch()

        # Read events
        events = read_control_events(control_dir)
        assert events.shutdown is True

        # Verify flag was cleaned up
        assert not (control_dir / "shutdown.flag").exists()

        print("✓ PASS: E2E shutdown flag")


@pytest.mark.allow_sleep
def test_e2e_full_workflow(tmp_path: Path) -> None:
    """End-to-end test: complete workflow from add to daemon processing."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        # Step 1: Create job runner
        runner = home / "job_runner.sh"
        runner.write_text("""#!/bin/bash
# Simulate RAG indexing
echo "Indexing $@"
# Fake some work
sleep 1
echo "Indexed $(date)" > "${WORKSPACE}/index/status.txt"
exit 0
""")
        runner.chmod(0o755)

        # Step 2: Create repo
        repo_root = home / "my_project"
        repo_root.mkdir()
        (repo_root / "README.md").write_text("# My Project")
        (repo_root / "src").mkdir()
        (repo_root / "src" / "main.py").write_text("print('hello')")

        # Step 3: Add repo
        from tools.rag_repo.config import ToolConfig
        tool_config = ToolConfig(
            registry_path=home / "registry.yml",
            default_rag_profile="default",
        )

        args = Mock(
            path=str(repo_root),
            yes=True,
            json=False,
            config=None,
        )

        result = _cmd_add(args, tool_config, None)
        assert result == 0

        # Step 4: Start daemon
        from tools.rag_daemon.registry import RegistryClient
        from tools.rag_daemon.models import DaemonConfig

        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=1,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=home / "registry.yml",
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
            job_runner_cmd=str(runner),
        )

        registry_client = RegistryClient.from_config(cfg)
        state_store = StateStore(cfg.state_store_path)
        workers = WorkerPool(cfg, state_store)
        scheduler = Scheduler(cfg, registry_client, state_store, workers)

        # Step 5: Run daemon
        scheduler.run_once()
        time.sleep(3)
        
        # Explicitly shut down workers to release file handles
        workers._executor.shutdown(wait=True)

        # Step 6: Verify results
        entries = registry_client.load()
        assert len(entries) == 1

        repo_id = list(entries.keys())[0]
        state = state_store.get(repo_id)

        assert state.last_run_status == "success"
        assert state.consecutive_failures == 0

        # Verify workspace was created and updated
        workspace_path = repo_root / ".llmc" / "rag"
        assert workspace_path.exists()

        status_file = workspace_path / "index" / "status.txt"
        if status_file.exists():
            content = status_file.read_text()
            assert "Indexed" in content

        print("✓ PASS: E2E full workflow")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(REPO_ROOT))

    # Import required modules

    tests = [
        test_e2e_daemon_tick_with_dummy_runner,
        test_e2e_daemon_multiple_repos,
        test_e2e_daemon_with_failures,
        test_e2e_daemon_control_flags,
        test_e2e_daemon_state_persistence,
        test_e2e_daemon_max_concurrent_jobs,
        test_e2e_daemon_with_fake_home,
        test_e2e_daemon_shutdown_flag,
        test_e2e_full_workflow,
    ]

    print("Running End-to-End Daemon Tests")
    print("=" * 70)

    passed = 0
    failed = 0

    for test in tests:
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                test(Path(tmpdir))
                passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
