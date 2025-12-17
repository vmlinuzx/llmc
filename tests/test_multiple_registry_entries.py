"""Tests for registry with multiple entries and various refresh intervals."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

import yaml

from llmc.rag_daemon.models import DaemonConfig, RepoState
from llmc.rag_daemon.registry import RegistryClient
from llmc.rag_daemon.scheduler import Scheduler
from llmc.rag_daemon.state_store import StateStore
from llmc.rag_daemon.workers import WorkerPool

UTC = UTC

# Calculate REPO_ROOT dynamically
REPO_ROOT = Path(__file__).resolve().parents[1]


def test_registry_multiple_entries_different_intervals(tmp_path: Path) -> None:
    """Registry with multiple repos respects different min_refresh_interval."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

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

        # Create registry with different refresh intervals
        registry_path = home / "repos.yml"
        registry_data = {
            "repos": [
                {
                    "repo_id": "repo-fast",
                    "repo_path": str(repo1),
                    "rag_workspace_path": str(repo1 / ".llmc" / "rag"),
                    "display_name": "Fast Repo",
                    "rag_profile": "default",
                    "min_refresh_interval_seconds": 60,  # 1 minute
                },
                {
                    "repo_id": "repo-normal",
                    "repo_path": str(repo2),
                    "rag_workspace_path": str(repo2 / ".llmc" / "rag"),
                    "display_name": "Normal Repo",
                    "rag_profile": "default",
                    "min_refresh_interval_seconds": 300,  # 5 minutes
                },
                {
                    "repo_id": "repo-slow",
                    "repo_path": str(repo3),
                    "rag_workspace_path": str(repo3 / ".llmc" / "rag"),
                    "display_name": "Slow Repo",
                    "rag_profile": "default",
                    "min_refresh_interval_seconds": 3600,  # 1 hour
                },
            ]
        }
        registry_path.write_text(yaml.dump(registry_data))

        # Create daemon config
        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=10,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=registry_path,
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
        )

        # Create daemon components
        registry = RegistryClient.from_config(cfg)
        state_store = StateStore(cfg.state_store_path)
        workers = WorkerPool(cfg, state_store)
        scheduler = Scheduler(cfg, registry, state_store, workers)

        now = datetime.now(UTC)

        # Set states: repo1 ran 30s ago, repo2 ran 4min ago, repo3 ran 30min ago
        states = {
            "repo-fast": RepoState(
                repo_id="repo-fast",
                last_run_status="success",
                last_run_finished_at=now - timedelta(seconds=30),  # 30s ago
            ),
            "repo-normal": RepoState(
                repo_id="repo-normal",
                last_run_status="success",
                last_run_finished_at=now - timedelta(minutes=4),  # 4min ago
            ),
            "repo-slow": RepoState(
                repo_id="repo-slow",
                last_run_status="success",
                last_run_finished_at=now - timedelta(minutes=30),  # 30min ago
            ),
        }

        # Mock dependencies
        with patch("tools.rag_daemon.scheduler.read_control_events") as mock_control:
            mock_control.return_value = Mock(
                refresh_all=False, refresh_repo_ids=set(), shutdown=False
            )

            with patch.object(state_store, "load_all", return_value=states):
                with patch.object(workers, "running_repo_ids", return_value=set()):
                    workers.submitted = []
                    scheduler._run_tick()

        # Verify results
        # repo-fast: 30s ago < 60s interval -> NOT eligible
        # repo-normal: 4min ago > 5min interval -> NOT eligible (wait, 4min < 5min)
        # Actually 4min < 5min, so also NOT eligible
        # repo-slow: 30min ago > 1hr interval -> NOT eligible
        # Wait, 30min < 1hr, so also NOT eligible
        #
        # Let me recalculate:
        # repo-fast: ran 30s ago, interval 60s -> 30s < 60s -> NOT eligible
        # repo-normal: ran 4min ago, interval 5min -> 4min < 5min -> NOT eligible
        # repo-slow: ran 30min ago, interval 60min -> 30min < 60min -> NOT eligible
        #
        # Actually, we need to set states such that some ARE eligible

        # Let me try again with different times
        states2 = {
            "repo-fast": RepoState(
                repo_id="repo-fast",
                last_run_status="success",
                last_run_finished_at=now - timedelta(seconds=90),  # 90s ago > 60s
            ),
            "repo-normal": RepoState(
                repo_id="repo-normal",
                last_run_status="success",
                last_run_finished_at=now - timedelta(minutes=6),  # 6min ago > 5min
            ),
            "repo-slow": RepoState(
                repo_id="repo-slow",
                last_run_status="success",
                last_run_finished_at=now - timedelta(minutes=90),  # 90min ago > 60min
            ),
        }

        with patch("tools.rag_daemon.scheduler.read_control_events") as mock_control:
            mock_control.return_value = Mock(
                refresh_all=False, refresh_repo_ids=set(), shutdown=False
            )

            with patch.object(state_store, "load_all", return_value=states2):
                with patch.object(workers, "running_repo_ids", return_value=set()):
                    workers.submitted = []
                    scheduler._run_tick()

        # All three should be eligible now
        assert len(workers.submitted) == 3, f"Expected 3 jobs, got {len(workers.submitted)}"

        submitted_ids = {job.repo.repo_id for job in workers.submitted}
        assert "repo-fast" in submitted_ids
        assert "repo-normal" in submitted_ids
        assert "repo-slow" in submitted_ids

        print("✓ PASS: Multiple repos with different intervals")


def test_registry_mixed_eligibility_states(tmp_path: Path) -> None:
    """Registry with mixed eligibility states (some eligible, some not)."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        # Create 5 repos
        repos = []
        for i in range(5):
            repo = home / f"repo{i}"
            repo.mkdir()
            (repo / "README.md").write_text(f"Repo {i}")
            repos.append(repo)

        # Create registry with varied intervals
        registry_path = home / "repos.yml"
        registry_data = {
            "repos": [
                {
                    "repo_id": f"repo{i}",
                    "repo_path": str(repos[i]),
                    "rag_workspace_path": str(repos[i] / ".llmc" / "rag"),
                    "display_name": f"Repo {i}",
                    "rag_profile": "default",
                    "min_refresh_interval_seconds": 300 if i % 2 == 0 else 60,
                }
                for i in range(5)
            ]
        }
        registry_path.write_text(yaml.dump(registry_data))

        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=10,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=registry_path,
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
        )

        registry = RegistryClient.from_config(cfg)
        state_store = StateStore(cfg.state_store_path)
        workers = WorkerPool(cfg, state_store)
        scheduler = Scheduler(cfg, registry, state_store, workers)

        now = datetime.now(UTC)

        # Create states: alternating eligibility
        # Even repos: interval 300s, ran 2min ago (120s) -> 120s < 300s -> NOT eligible
        # Odd repos: interval 60s, ran 2min ago (120s) -> 120s > 60s -> eligible
        states = {
            f"repo{i}": RepoState(
                repo_id=f"repo{i}",
                last_run_status="success",
                last_run_finished_at=now - timedelta(minutes=2),
            )
            for i in range(5)
        }

        with patch("tools.rag_daemon.scheduler.read_control_events") as mock_control:
            mock_control.return_value = Mock(
                refresh_all=False, refresh_repo_ids=set(), shutdown=False
            )

            with patch.object(state_store, "load_all", return_value=states):
                with patch.object(workers, "running_repo_ids", return_value=set()):
                    workers.submitted = []
                    scheduler._run_tick()

        # Only odd repos should be eligible (intervals: 60s, ran 120s ago)
        submitted_ids = {job.repo.repo_id for job in workers.submitted}

        # Odd indices (1, 3) should be eligible
        assert "repo1" in submitted_ids
        assert "repo3" in submitted_ids

        # Even indices (0, 2, 4) should NOT be eligible
        assert "repo0" not in submitted_ids
        assert "repo2" not in submitted_ids
        assert "repo4" not in submitted_ids

        # Should have exactly 2 jobs
        assert len(workers.submitted) == 2

        print("✓ PASS: Mixed eligibility states")


def test_registry_with_none_intervals(tmp_path: Path) -> None:
    """Registry entries without explicit interval use default (tick_interval)."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        # Create repos
        repo1 = home / "repo1"
        repo1.mkdir()
        (repo1 / "README.md").write_text("Repo 1")

        repo2 = home / "repo2"
        repo2.mkdir()
        (repo2 / "README.md").write_text("Repo 2")

        # Create registry: one with interval, one without
        registry_path = home / "repos.yml"
        registry_data = {
            "repos": [
                {
                    "repo_id": "repo-with-interval",
                    "repo_path": str(repo1),
                    "rag_workspace_path": str(repo1 / ".llmc" / "rag"),
                    "display_name": "Repo With Interval",
                    "rag_profile": "default",
                    "min_refresh_interval_seconds": 300,  # 5 minutes
                },
                {
                    "repo_id": "repo-no-interval",
                    "repo_path": str(repo2),
                    "rag_workspace_path": str(repo2 / ".llmc" / "rag"),
                    "display_name": "Repo No Interval",
                    "rag_profile": "default",
                    # No interval specified - should use default (tick_interval = 60s)
                },
            ]
        }
        registry_path.write_text(yaml.dump(registry_data))

        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=10,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=registry_path,
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
        )

        registry = RegistryClient.from_config(cfg)
        state_store = StateStore(cfg.state_store_path)
        workers = WorkerPool(cfg, state_store)
        scheduler = Scheduler(cfg, registry, state_store, workers)

        now = datetime.now(UTC)

        # Both repos ran 90 seconds ago
        # repo-with-interval: 90s < 300s -> NOT eligible
        # repo-no-interval: 90s > 60s -> eligible
        states = {
            "repo-with-interval": RepoState(
                repo_id="repo-with-interval",
                last_run_status="success",
                last_run_finished_at=now - timedelta(seconds=90),
            ),
            "repo-no-interval": RepoState(
                repo_id="repo-no-interval",
                last_run_status="success",
                last_run_finished_at=now - timedelta(seconds=90),
            ),
        }

        with patch("tools.rag_daemon.scheduler.read_control_events") as mock_control:
            mock_control.return_value = Mock(
                refresh_all=False, refresh_repo_ids=set(), shutdown=False
            )

            with patch.object(state_store, "load_all", return_value=states):
                with patch.object(workers, "running_repo_ids", return_value=set()):
                    workers.submitted = []
                    scheduler._run_tick()

        # Only repo-no-interval should be eligible
        submitted_ids = {job.repo.repo_id for job in workers.submitted}
        assert "repo-no-interval" in submitted_ids
        assert "repo-with-interval" not in submitted_ids
        assert len(workers.submitted) == 1

        print("✓ PASS: Default interval handling")


def test_registry_load_all_entries(tmp_path: Path) -> None:
    """Registry.load_all() returns all registered entries."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        # Create repos
        repos = []
        for i in range(5):
            repo = home / f"repo{i}"
            repo.mkdir()
            (repo / "README.md").write_text(f"Repo {i}")
            repos.append(repo)

        # Create registry with 5 entries
        registry_path = home / "repos.yml"
        registry_data = {
            "repos": [
                {
                    "repo_id": f"repo{i}",
                    "repo_path": str(repos[i]),
                    "rag_workspace_path": str(repos[i] / ".llmc" / "rag"),
                    "display_name": f"Repo {i}",
                    "rag_profile": "default",
                    "min_refresh_interval_seconds": 60,
                }
                for i in range(5)
            ]
        }
        registry_path.write_text(yaml.dump(registry_data))

        # Load via RegistryClient
        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=2,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=registry_path,
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
        )

        registry = RegistryClient.from_config(cfg)
        entries = registry.load()

        # Verify all 5 entries loaded
        assert len(entries) == 5, f"Expected 5 entries, got {len(entries)}"

        for i in range(5):
            repo_id = f"repo{i}"
            assert repo_id in entries, f"Missing entry: {repo_id}"

            entry = entries[repo_id]
            assert entry.repo_id == repo_id
            assert entry.repo_path == repos[i]
            assert entry.rag_workspace_path == repos[i] / ".llmc" / "rag"
            assert entry.display_name == f"Repo {i}"
            assert entry.rag_profile == "default"

        print("✓ PASS: Load all entries")


def test_registry_empty_file(tmp_path: Path) -> None:
    """Registry with empty file returns empty dict."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        registry_path = home / "empty.yml"
        registry_path.write_text("repos: []\n")

        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=2,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=registry_path,
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
        )

        registry = RegistryClient.from_config(cfg)
        entries = registry.load()

        assert len(entries) == 0
        assert isinstance(entries, dict)

        print("✓ PASS: Empty registry")


def test_registry_nonexistent_file(tmp_path: Path) -> None:
    """Registry with non-existent file returns empty dict (doesn't crash)."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        registry_path = home / "nonexistent.yml"
        assert not registry_path.exists()

        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=2,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=registry_path,
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
        )

        registry = RegistryClient.from_config(cfg)
        entries = registry.load()

        assert len(entries) == 0
        assert isinstance(entries, dict)

        print("✓ PASS: Non-existent registry file")


def test_registry_invalid_paths(tmp_path: Path) -> None:
    """Registry with invalid repo paths doesn't crash on load."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        # Create registry with non-existent paths
        registry_path = home / "bad_paths.yml"
        registry_data = {
            "repos": [
                {
                    "repo_id": "repo-invalid1",
                    "repo_path": "/does/not/exist",
                    "rag_workspace_path": "/does/not/exist/.llmc/rag",
                    "display_name": "Invalid Repo 1",
                    "rag_profile": "default",
                },
                {
                    "repo_id": "repo-invalid2",
                    "repo_path": str(home / "also_missing"),
                    "rag_workspace_path": str(home / "also_missing" / ".llmc" / "rag"),
                    "display_name": "Invalid Repo 2",
                    "rag_profile": "default",
                },
            ]
        }
        registry_path.write_text(yaml.dump(registry_data))

        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=2,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=registry_path,
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
        )

        # Should not crash on load
        registry = RegistryClient.from_config(cfg)
        entries = registry.load()

        # Invalid paths are still loaded (validation is separate concern)
        assert len(entries) == 2
        assert "repo-invalid1" in entries
        assert "repo-invalid2" in entries

        print("✓ PASS: Invalid paths don't crash")


def test_registry_timedelta_intervals(tmp_path: Path) -> None:
    """Registry entries can use timedelta objects for intervals."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        repo = home / "repo"
        repo.mkdir()
        (repo / "README.md").write_text("Repo")

        # Use timedelta in YAML (will be string in file, parsed as seconds)
        registry_path = home / "repos.yml"
        registry_data = {
            "repos": [
                {
                    "repo_id": "repo-timedelta",
                    "repo_path": str(repo),
                    "rag_workspace_path": str(repo / ".llmc" / "rag"),
                    "display_name": "Repo with Timedelta",
                    "rag_profile": "default",
                    "min_refresh_interval_seconds": 180,  # 3 minutes
                }
            ]
        }
        registry_path.write_text(yaml.dump(registry_data))

        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=2,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=registry_path,
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
        )

        registry = RegistryClient.from_config(cfg)
        entries = registry.load()

        assert len(entries) == 1
        entry = entries["repo-timedelta"]

        # Verify interval is parsed correctly
        assert entry.min_refresh_interval == timedelta(seconds=180)

        print("✓ PASS: Timedelta intervals")


def test_registry_force_refresh_all(tmp_path: Path) -> None:
    """refresh_all flag forces all repos to refresh regardless of intervals."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        # Create 3 repos with different intervals
        repos = []
        for i in range(3):
            repo = home / f"repo{i}"
            repo.mkdir()
            (repo / "README.md").write_text(f"Repo {i}")
            repos.append(repo)

        registry_path = home / "repos.yml"
        registry_data = {
            "repos": [
                {
                    "repo_id": f"repo{i}",
                    "repo_path": str(repos[i]),
                    "rag_workspace_path": str(repos[i] / ".llmc" / "rag"),
                    "display_name": f"Repo {i}",
                    "rag_profile": "default",
                    "min_refresh_interval_seconds": 300 if i == 0 else 600,
                }
                for i in range(3)
            ]
        }
        registry_path.write_text(yaml.dump(registry_data))

        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=10,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=registry_path,
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
        )

        registry = RegistryClient.from_config(cfg)
        state_store = StateStore(cfg.state_store_path)
        workers = WorkerPool(cfg, state_store)
        scheduler = Scheduler(cfg, registry, state_store, workers)

        now = datetime.now(UTC)

        # All repos ran just 10 seconds ago (shouldn't be eligible)
        states = {
            f"repo{i}": RepoState(
                repo_id=f"repo{i}",
                last_run_status="success",
                last_run_finished_at=now - timedelta(seconds=10),
            )
            for i in range(3)
        }

        # Without refresh_all - no jobs should be scheduled
        with patch("tools.rag_daemon.scheduler.read_control_events") as mock_control:
            mock_control.return_value = Mock(
                refresh_all=False, refresh_repo_ids=set(), shutdown=False
            )

            with patch.object(state_store, "load_all", return_value=states):
                with patch.object(workers, "running_repo_ids", return_value=set()):
                    workers.submitted = []
                    scheduler._run_tick()

        assert len(workers.submitted) == 0, "No jobs without refresh_all"

        # With refresh_all - all jobs should be scheduled
        with patch("tools.rag_daemon.scheduler.read_control_events") as mock_control:
            mock_control.return_value = Mock(
                refresh_all=True, refresh_repo_ids=set(), shutdown=False
            )

            with patch.object(state_store, "load_all", return_value=states):
                with patch.object(workers, "running_repo_ids", return_value=set()):
                    workers.submitted = []
                    scheduler._run_tick()

        assert len(workers.submitted) == 3, "All jobs with refresh_all"

        submitted_ids = {job.repo.repo_id for job in workers.submitted}
        for i in range(3):
            assert f"repo{i}" in submitted_ids

        # Verify force flag is set
        for job in workers.submitted:
            assert job.force is True

        print("✓ PASS: Force refresh all")


def test_registry_force_specific_repo(tmp_path: Path) -> None:
    """refresh_<repo_id>.flag forces specific repo to refresh."""
    with tempfile.TemporaryDirectory() as home:
        home = Path(home)

        # Create repos
        repos = []
        for i in range(3):
            repo = home / f"repo{i}"
            repo.mkdir()
            (repo / "README.md").write_text(f"Repo {i}")
            repos.append(repo)

        registry_path = home / "repos.yml"
        registry_data = {
            "repos": [
                {
                    "repo_id": f"repo{i}",
                    "repo_path": str(repos[i]),
                    "rag_workspace_path": str(repos[i] / ".llmc" / "rag"),
                    "display_name": f"Repo {i}",
                    "rag_profile": "default",
                }
                for i in range(3)
            ]
        }
        registry_path.write_text(yaml.dump(registry_data))

        cfg = DaemonConfig(
            tick_interval_seconds=60,
            max_concurrent_jobs=10,
            max_consecutive_failures=3,
            base_backoff_seconds=60,
            max_backoff_seconds=3600,
            registry_path=registry_path,
            state_store_path=home / "state",
            log_path=home / "logs",
            control_dir=home / "control",
        )

        registry = RegistryClient.from_config(cfg)
        state_store = StateStore(cfg.state_store_path)
        workers = WorkerPool(cfg, state_store)
        scheduler = Scheduler(cfg, registry, state_store, workers)

        now = datetime.now(UTC)

        # All repos ran recently
        states = {
            f"repo{i}": RepoState(
                repo_id=f"repo{i}",
                last_run_status="success",
                last_run_finished_at=now - timedelta(seconds=10),
            )
            for i in range(3)
        }

        # Force refresh only repo1
        with patch("tools.rag_daemon.scheduler.read_control_events") as mock_control:
            mock_control.return_value = Mock(
                refresh_all=False, refresh_repo_ids={"repo1"}, shutdown=False
            )

            with patch.object(state_store, "load_all", return_value=states):
                with patch.object(workers, "running_repo_ids", return_value=set()):
                    workers.submitted = []
                    scheduler._run_tick()

        # Only repo1 should be scheduled
        assert len(workers.submitted) == 1
        assert workers.submitted[0].repo.repo_id == "repo1"
        assert workers.submitted[0].force is True

        print("✓ PASS: Force specific repo")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(REPO_ROOT))

    tests = [
        test_registry_multiple_entries_different_intervals,
        test_registry_mixed_eligibility_states,
        test_registry_with_none_intervals,
        test_registry_load_all_entries,
        test_registry_empty_file,
        test_registry_nonexistent_file,
        test_registry_invalid_paths,
        test_registry_timedelta_intervals,
        test_registry_force_refresh_all,
        test_registry_force_specific_repo,
    ]

    print("Running Multiple Registry Entries Tests")
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
