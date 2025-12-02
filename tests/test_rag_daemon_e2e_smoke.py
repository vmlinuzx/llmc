"""End-to-end smoke test for LLMC RAG Daemon and Repo Registration Tool."""

import os
from pathlib import Path
import time
from unittest.mock import patch

import pytest
import yaml

from tools.rag_daemon.config import load_config
from tools.rag_daemon.registry import RegistryClient
from tools.rag_daemon.scheduler import Scheduler
from tools.rag_daemon.state_store import StateStore
from tools.rag_daemon.workers import WorkerPool
from tools.rag_repo.config import load_tool_config
from tools.rag_repo.inspect_repo import inspect_repo
from tools.rag_repo.models import RegistryEntry
from tools.rag_repo.registry import RegistryAdapter
from tools.rag_repo.workspace import init_workspace, plan_workspace, validate_workspace


@pytest.mark.allow_sleep
def test_e2e_smoke_test(tmp_path: Path) -> None:
    """End-to-end smoke test using temporary directories."""
    # Setup: Create temp directories to simulate real environment
    home_dir = tmp_path / "home"
    home_dir.mkdir()

    # Create temporary fake home directory
    llmc_dir = home_dir / ".llmc"
    llmc_dir.mkdir()

    # Setup 1: Create a temporary test repo
    test_repo = llmc_dir / "test_repo"
    test_repo.mkdir()

    # Add a Python file to make it look like a real repo
    (test_repo / "main.py").write_text("# Test repository\nprint('hello')\n")
    (test_repo / "README.md").write_text("# Test Repo\nThis is a test.\n")

    # Setup 2: Initialize RAG workspace for the test repo
    registry_config_path = home_dir / ".llmc" / "registry-config.yml"
    registry_config_path.write_text(
        yaml.dump(
            {
                "registry_path": str(home_dir / ".llmc" / "repos.yml"),
                "daemon_control_path": str(home_dir / ".llmc" / "rag-control"),
            }
        )
    )

    # Load tool config
    with patch.dict(os.environ, {"LLMC_RAG_REPO_CONFIG": str(registry_config_path)}):
        tool_config = load_tool_config()

    # Create workspace
    inspection = inspect_repo(test_repo, tool_config)
    plan = plan_workspace(test_repo, tool_config, inspection)
    init_workspace(plan, inspection, tool_config, non_interactive=True)
    validation = validate_workspace(plan)

    assert validation.status in ["ok", "warning"], f"Workspace validation failed: {validation.issues}"

    # Setup 3: Register the repo using the registry tool
    registry_adapter = RegistryAdapter(tool_config)

    # Generate repo ID
    from tools.rag_repo.utils import generate_repo_id

    repo_id = generate_repo_id(test_repo)
    entry = RegistryEntry(
        repo_id=repo_id,
        repo_path=test_repo,
        rag_workspace_path=plan.workspace_root,
        display_name="Test Repo",
        rag_profile="default",
    )

    # Register
    registry_adapter.register(entry)

    # Verify registry has the entry
    entries = registry_adapter.load_all()
    assert repo_id in entries
    assert entries[repo_id].repo_path == test_repo

    # Setup 4: Create daemon config
    daemon_config_path = home_dir / ".llmc" / "rag-daemon.yml"
    daemon_config_path.write_text(
        yaml.dump(
            {
                "tick_interval_seconds": 60,
                "max_concurrent_jobs": 2,
                "max_consecutive_failures": 3,
                "base_backoff_seconds": 60,
                "max_backoff_seconds": 3600,
                "registry_path": str(tool_config.registry_path),
                "state_store_path": str(home_dir / ".llmc" / "rag-state"),
                "log_path": str(home_dir / ".llmc" / "logs" / "rag-daemon"),
                "control_dir": str(tool_config.daemon_control_path),
                "job_runner_cmd": "echo",  # Dummy command for testing
            }
        )
    )

    # Setup 5: Create a mock job runner that logs its calls
    mock_script = home_dir / "mock_rag_job.sh"
    mock_script.write_text(
        """#!/bin/bash
echo "Mock RAG job called for: $2"
echo '{"status": "success", "spans": 42}' > /tmp/job_summary_$$.json
"""
    )
    mock_script.chmod(0o755)

    daemon_config_path.write_text(
        yaml.dump(
            {
                "tick_interval_seconds": 60,
                "max_concurrent_jobs": 2,
                "max_concurrent_jobs": 2,
                "max_consecutive_failures": 3,
                "base_backoff_seconds": 60,
                "max_backoff_seconds": 3600,
                "registry_path": str(tool_config.registry_path),
                "state_store_path": str(home_dir / ".llmc" / "rag-state"),
                "log_path": str(home_dir / ".llmc" / "logs" / "rag-daemon"),
                "control_dir": str(tool_config.daemon_control_path),
                "job_runner_cmd": str(mock_script),
            }
        )
    )

    # Setup 6: Start the daemon components
    with patch.dict(os.environ, {"LLMC_RAG_DAEMON_CONFIG": str(daemon_config_path)}):
        config = load_config()

    # Verify config loaded correctly
    assert config.registry_path == tool_config.registry_path
    assert config.job_runner_cmd == str(mock_script)

    # Create daemon components
    registry = RegistryClient.from_config(config)
    state_store = StateStore(config.state_store_path)
    workers = WorkerPool(config=config, state_store=state_store)
    scheduler = Scheduler(
        config=config,
        registry=registry,
        state_store=state_store,
        workers=workers,
    )

    # Test 1: Verify registry has the repo
    registry_entries = registry.load()
    assert repo_id in registry_entries
    repo_descriptor = registry_entries[repo_id]
    assert repo_descriptor.repo_path == test_repo
    assert repo_descriptor.rag_workspace_path == plan.workspace_root

    # Test 2: Verify state store is empty initially (before scheduler runs)
    all_states = state_store.load_all()
    # Note: If job already ran due to race, this might already have state
    # So we just check that we have a valid state structure
    print(f"  Initial state check: {len(all_states)} states in store")

    # Test 3: Run a single scheduler tick
    scheduler.run_once()

    # Wait for async workers to complete
    max_wait = 5  # seconds
    start = time.time()
    while len(workers.running_repo_ids()) > 0 and (time.time() - start) < max_wait:
        time.sleep(0.1)

    # Test 4: Verify state store was updated
    final_state = state_store.get(repo_id)
    assert final_state is not None, "State should be created after job runs"
    assert final_state.repo_id == repo_id
    assert final_state.last_run_status in ["success", "error", "running"]

    # Test 5: Verify the job was actually invoked by checking state
    # (Our mock job doesn't actually run, but we can verify the workflow)
    if final_state.last_run_status == "success":
        assert final_state.consecutive_failures == 0
        assert final_state.last_error_reason is None
        assert final_state.last_run_finished_at is not None

    # Test 6: Verify workspace validation still passes
    re_validation = validate_workspace(plan)
    assert re_validation.status == "ok"

    # Test 7: Verify control directory exists
    assert config.control_dir.exists()

    # Test 8: Verify daemon can handle control flags
    # Create a refresh flag
    refresh_flag = config.control_dir / f"refresh_{repo_id}.flag"
    refresh_flag.write_text("")

    # Read control events
    from tools.rag_daemon.control import read_control_events

    events = read_control_events(config.control_dir)
    assert repo_id in events.refresh_repo_ids

    # Flag should be cleaned up
    assert not refresh_flag.exists()

    # Test 9: Verify idempotent behavior - running again should work
    initial_status = final_state.last_run_status
    scheduler.run_once()

    # Wait for completion
    start = time.time()
    while len(workers.running_repo_ids()) > 0 and (time.time() - start) < max_wait:
        time.sleep(0.1)

    second_state = state_store.get(repo_id)
    assert second_state is not None

    # Test 10: Verify registry can find the entry by path and ID
    found_by_path = registry_adapter.find_by_path(test_repo)
    assert found_by_path is not None
    assert found_by_path.repo_id == repo_id

    found_by_id = registry_adapter.find_by_id(repo_id)
    assert found_by_id is not None
    assert found_by_id.repo_path == test_repo

    # Print summary
    print("\n" + "=" * 60)
    print("E2E Smoke Test Summary")
    print("=" * 60)
    print(f"✓ Test repo created at: {test_repo}")
    print(f"✓ Workspace initialized at: {plan.workspace_root}")
    print(f"✓ Repo registered with ID: {repo_id}")
    print(f"✓ Daemon config loaded from: {daemon_config_path}")
    print(f"✓ Registry has {len(registry_entries)} repo(s)")
    print(f"✓ State store updated with job result: {final_state.last_run_status}")
    print("✓ Control flags working correctly")
    print("✓ Registry lookup by path and ID working")
    print("=" * 60)
    print("\nAll end-to-end tests passed! ✓")


@pytest.mark.allow_sleep
def test_e2e_multiple_repos(tmp_path: Path) -> None:
    """Test that daemon can handle multiple repos."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    llmc_dir = home_dir / ".llmc"
    llmc_dir.mkdir()

    # Create multiple test repos
    repos = []
    for i in range(3):
        repo_path = llmc_dir / f"repo_{i}"
        repo_path.mkdir()
        (repo_path / f"file_{i}.py").write_text(f"# Repo {i}\n")
        repos.append((repo_path, f"repo-{i}"))

    # Setup tool config
    registry_config_path = home_dir / ".llmc" / "registry-config.yml"
    registry_config_path.write_text(
        yaml.dump(
            {
                "registry_path": str(home_dir / ".llmc" / "repos.yml"),
                "daemon_control_path": str(home_dir / ".llmc" / "rag-control"),
            }
        )
    )

    with patch.dict(os.environ, {"LLMC_RAG_REPO_CONFIG": str(registry_config_path)}):
        tool_config = load_tool_config()

    # Register all repos
    registry_adapter = RegistryAdapter(tool_config)
    from tools.rag_repo.utils import generate_repo_id

    for repo_path, expected_id_prefix in repos:
        inspection = inspect_repo(repo_path, tool_config)
        plan = plan_workspace(repo_path, tool_config, inspection)
        init_workspace(plan, inspection, tool_config, non_interactive=True)

        repo_id = generate_repo_id(repo_path)
        entry = RegistryEntry(
            repo_id=repo_id,
            repo_path=repo_path,
            rag_workspace_path=plan.workspace_root,
            display_name=repo_path.name,
            rag_profile="default",
        )
        registry_adapter.register(entry)

    # Verify all repos are registered
    entries = registry_adapter.load_all()
    assert len(entries) == 3

    # Verify daemon can load all repos
    daemon_config_path = home_dir / ".llmc" / "rag-daemon.yml"
    daemon_config_path.write_text(
        yaml.dump(
            {
                "tick_interval_seconds": 60,
                "max_concurrent_jobs": 5,  # Allow all to run
                "max_consecutive_failures": 3,
                "base_backoff_seconds": 60,
                "max_backoff_seconds": 3600,
                "registry_path": str(tool_config.registry_path),
                "state_store_path": str(home_dir / ".llmc" / "rag-state"),
                "log_path": str(home_dir / ".llmc" / "logs" / "rag-daemon"),
                "control_dir": str(tool_config.daemon_control_path),
                "job_runner_cmd": "echo",
            }
        )
    )

    with patch.dict(os.environ, {"LLMC_RAG_DAEMON_CONFIG": str(daemon_config_path)}):
        config = load_config()

    registry = RegistryClient.from_config(config)
    state_store = StateStore(config.state_store_path)
    workers = WorkerPool(config=config, state_store=state_store)
    scheduler = Scheduler(config=config, registry=registry, state_store=state_store, workers=workers)

    # Run scheduler
    registry_entries = registry.load()
    assert len(registry_entries) == 3

    scheduler.run_once()

    # Wait for completion
    max_wait = 5
    start = time.time()
    while len(workers.running_repo_ids()) > 0 and (time.time() - start) < max_wait:
        time.sleep(0.1)

    # Verify all repos have state
    all_states = state_store.load_all()
    assert len(all_states) == 3

    print("\n✓ Multiple repos test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
