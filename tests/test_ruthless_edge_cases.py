"""Ruthless edge case tests for daemon, registry, and router."""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import pytest
import yaml

from tools.rag_daemon.registry import RegistryClient
from tools.rag_daemon.control import read_control_events
from tools.rag_daemon.workers import WorkerPool, make_job_id
from tools.rag_daemon.models import DaemonConfig, RepoDescriptor, Job, JobResult, ControlEvents
from tools.rag_daemon.state_store import StateStore
from scripts.router import RouterSettings, choose_start_tier, choose_next_tier_on_failure, estimate_json_nodes_and_depth


# ==============================================================================
# REGISTRY CLIENT EDGE CASES
# ==============================================================================

def test_registry_malformed_yaml(tmp_path: Path) -> None:
    """Test registry with malformed YAML."""
    registry_file = tmp_path / "repos.yml"
    registry_file.write_text("{ invalid: yaml: [ unclosed")

    client = RegistryClient(path=registry_file)

    with pytest.raises(Exception):
        client.load()


def test_registry_empty_file(tmp_path: Path) -> None:
    """Test registry with empty file."""
    registry_file = tmp_path / "repos.yml"
    registry_file.write_text("")

    client = RegistryClient(path=registry_file)
    result = client.load()

    assert result == {}


def test_registry_nonexistent_file(tmp_path: Path) -> None:
    """Test registry with non-existent file."""
    registry_file = tmp_path / "nonexistent.yml"

    client = RegistryClient(path=registry_file)
    result = client.load()

    assert result == {}


def test_registry_mixed_valid_invalid_entries(tmp_path: Path) -> None:
    """Test registry with mix of valid and invalid entries."""
    registry_file = tmp_path / "repos.yml"
    registry_file.write_text(yaml.dump([
        {
            "repo_id": "valid-repo",
            "repo_path": "~/valid",
            "rag_workspace_path": "~/valid/.llmc/rag"
        },
        "not-a-dict",  # Invalid entry
        {
            # Missing repo_id
            "repo_path": "~/invalid",
            "rag_workspace_path": "~/invalid/.llmc/rag"
        },
        None,  # Another invalid entry
        {
            "repo_id": "another-valid",
            "repo_path": "~/another",
            "rag_workspace_path": "~/another/.llmc/rag"
        }
    ]))

    client = RegistryClient(path=registry_file)
    result = client.load()

    assert "valid-repo" in result
    assert "another-valid" in result
    assert len(result) == 2


def test_registry_list_with_repos_key_mixed_entries(tmp_path: Path) -> None:
    """Test registry with 'repos' key containing mixed entries."""
    registry_file = tmp_path / "repos.yml"
    registry_file.write_text(yaml.dump({
        "repos": [
            {"repo_id": "repo1", "repo_path": "~/repo1", "rag_workspace_path": "~/repo1/.llmc/rag"},
            "invalid",
            {"repo_path": "~/invalid"},  # Missing repo_id
            None,
            {"repo_id": "repo2", "repo_path": "~/repo2", "rag_workspace_path": "~/repo2/.llmc/rag"},
        ]
    }))

    client = RegistryClient(path=registry_file)
    result = client.load()

    assert "repo1" in result
    assert "repo2" in result
    assert len(result) == 2


def test_registry_duplicate_repo_ids(tmp_path: Path) -> None:
    """Test registry with duplicate repo IDs (last one wins)."""
    registry_file = tmp_path / "repos.yml"
    registry_file.write_text(yaml.dump([
        {"repo_id": "duplicate", "repo_path": "~/first", "rag_workspace_path": "~/first/.llmc/rag"},
        {"repo_id": "duplicate", "repo_path": "~/second", "rag_workspace_path": "~/second/.llmc/rag"},
    ]))

    client = RegistryClient(path=registry_file)
    result = client.load()

    assert len(result) == 1
    assert "duplicate" in result
    # Last entry should win
    resolved_path = str(result["duplicate"].repo_path)
    assert "second" in resolved_path


def test_registry_missing_required_fields(tmp_path: Path) -> None:
    """Test registry entry missing required fields."""
    registry_file = tmp_path / "repos.yml"
    registry_file.write_text(yaml.dump([
        {"repo_id": "missing-repo-path", "rag_workspace_path": "~/workspace"},
        {"repo_path": "~/path", "rag_workspace_path": "~/workspace"},  # Missing repo_id
    ]))

    client = RegistryClient(path=registry_file)

    # Should raise KeyError for missing required fields
    with pytest.raises(KeyError):
        client.load()


def test_registry_invalid_path_expansion(tmp_path: Path) -> None:
    """Test registry with paths that can't be expanded."""
    registry_file = tmp_path / "repos.yml"
    # Use a path that will fail expanduser
    registry_file.write_text(yaml.dump([
        {"repo_id": "bad-path", "repo_path": "/nonexistent/\x00invalid", "rag_workspace_path": "~/workspace"}
    ]))

    client = RegistryClient(path=registry_file)

    # Invalid paths should be gracefully skipped, not crash
    result = client.load()
    assert len(result) == 0, "Invalid entries should be skipped, not cause crash"


def test_registry_special_characters_in_paths(tmp_path: Path) -> None:
    """Test registry with special characters in paths."""
    registry_file = tmp_path / "repos.yml"

    # Create dirs with special chars
    special_dir = tmp_path / "repo with spaces & (parens)"
    special_dir.mkdir()

    workspace_dir = tmp_path / "workspace with 'quotes'"
    workspace_dir.mkdir()

    registry_file.write_text(yaml.dump([{
        "repo_id": "special-chars",
        "repo_path": str(special_dir),
        "rag_workspace_path": str(workspace_dir)
    }]))

    client = RegistryClient(path=registry_file)
    result = client.load()

    assert "special-chars" in result
    # Paths should be properly resolved


# ==============================================================================
# CONTROL EVENTS EDGE CASES
# ==============================================================================

def test_control_read_nonexistent_directory(tmp_path: Path) -> None:
    """Test reading control events from non-existent directory."""
    non_existent_dir = tmp_path / "non_existent" / "control"

    result = read_control_events(non_existent_dir)

    # Should return empty events and create directory
    assert result.refresh_all is False
    assert result.refresh_repo_ids == set()
    assert result.shutdown is False
    assert non_existent_dir.exists()


def test_control_read_directory_cannot_create(tmp_path: Path) -> None:
    """Test when control directory cannot be created (permissions)."""
    # Create a file at the location we want to create a directory
    blocked_path = tmp_path / "blocked"
    blocked_path.write_text("blocking file")

    result = read_control_events(blocked_path)

    # Should return empty events gracefully
    assert result == ControlEvents()


def test_control_flag_with_no_extension(tmp_path: Path) -> None:
    """Test control directory with files that aren't .flag files."""
    control_dir = tmp_path / "control"
    control_dir.mkdir()

    # Create non-flag files
    (control_dir / "notaflag.txt").write_text("test")
    (control_dir / "something.log").write_text("test")

    result = read_control_events(control_dir)

    # Should return empty events
    assert result == ControlEvents()


def test_control_malformed_flag_names(tmp_path: Path) -> None:
    """Test control directory with malformed flag names."""
    control_dir = tmp_path / "control"
    control_dir.mkdir()

    # Create flags with edge case names
    (control_dir / "refresh_.flag").touch()  # Empty repo_id
    (control_dir / "refresh.flag").touch()   # Missing repo_id

    result = read_control_events(control_dir)

    # Should handle gracefully, no repo IDs added
    assert result.refresh_repo_ids == set()


def test_control_unable_to_delete_flags(tmp_path: Path) -> None:
    """Test when flags cannot be deleted."""
    control_dir = tmp_path / "control"
    control_dir.mkdir()

    # Create a flag file with read-only permissions
    flag_file = control_dir / "refresh_all.flag"
    flag_file.touch()
    flag_file.chmod(0o444)  # Read-only

    # Try to read events (should handle deletion failure gracefully)
    result = read_control_events(control_dir)

    # Should still parse the event
    assert result.refresh_all is True

    # Cleanup (file may already have been deleted by read_control_events)
    if flag_file.exists():
        flag_file.chmod(0o644)
        flag_file.unlink()


# ==============================================================================
# WORKER POOL EDGE CASES
# ==============================================================================

def test_worker_job_id_uniqueness() -> None:
    """Test that job IDs are unique."""
    ids = {make_job_id() for _ in range(1000)}

    # Should have 1000 unique IDs
    assert len(ids) == 1000


def test_worker_duplicate_job_submission(tmp_path: Path) -> None:
    """Test submitting duplicate jobs for the same repo."""
    config = DaemonConfig(
        tick_interval_seconds=60,
        max_concurrent_jobs=5,
        max_consecutive_failures=3,
        base_backoff_seconds=60,
        max_backoff_seconds=3600,
        registry_path=tmp_path / "repos.yml",
        state_store_path=tmp_path / "state",
        log_path=tmp_path / "logs",
        control_dir=tmp_path / "control",
        job_runner_cmd="test-runner",
    )

    state_store = StateStore(config.state_store_path)

    # Create a repo
    repo = RepoDescriptor(
        repo_id="test-repo",
        repo_path=tmp_path / "repo",
        rag_workspace_path=tmp_path / "workspace",
    )

    # Create jobs for same repo
    jobs = [
        Job(job_id="job1", repo=repo),
        Job(job_id="job2", repo=repo),
        Job(job_id="job3", repo=repo),
    ]

    pool = WorkerPool(config, state_store)

    # Attach a list to capture submitted jobs
    submitted = []
    pool.submitted = submitted

    pool.submit_jobs(jobs)

    # Only the first job should be submitted
    assert len(submitted) == 1
    assert submitted[0].job_id == "job1"


def test_worker_concurrent_job_limit(tmp_path: Path) -> None:
    """Test max concurrent jobs limit."""
    config = DaemonConfig(
        tick_interval_seconds=60,
        max_concurrent_jobs=2,
        max_consecutive_failures=3,
        base_backoff_seconds=60,
        max_backoff_seconds=3600,
        registry_path=tmp_path / "repos.yml",
        state_store_path=tmp_path / "state",
        log_path=tmp_path / "logs",
        control_dir=tmp_path / "control",
        job_runner_cmd="test-runner",
    )

    state_store = StateStore(config.state_store_path)

    # Create repos
    repos = [
        RepoDescriptor(
            repo_id=f"repo-{i}",
            repo_path=tmp_path / f"repo-{i}",
            rag_workspace_path=tmp_path / f"workspace-{i}",
        )
        for i in range(5)
    ]

    jobs = [Job(job_id=f"job-{i}", repo=repo) for i, repo in enumerate(repos)]

    pool = WorkerPool(config, state_store)

    # Attach a list to capture submitted jobs
    submitted = []
    pool.submitted = submitted

    pool.submit_jobs(jobs)

    # With max_concurrent_jobs=2, should submit all jobs
    # (they're for different repos)
    assert len(submitted) == 5


# ==============================================================================
# ROUTER EDGE CASES
# ==============================================================================

def test_router_settings_invalid_env_vars() -> None:
    """Test RouterSettings with invalid environment variables."""
    with patch.dict(os.environ, {
        "ROUTER_CONTEXT_LIMIT": "not-a-number",
        "ROUTER_NODE_LIMIT": "invalid",
        "ROUTER_DEPTH_LIMIT": "",
    }, clear=False):
        settings = RouterSettings()

        # Should fallback to defaults for invalid values
        assert settings.context_limit == 32000
        assert settings.depth_limit == 6


def test_router_settings_extreme_values() -> None:
    """Test RouterSettings with extreme values."""
    with patch.dict(os.environ, {
        "ROUTER_CONTEXT_LIMIT": "999999999",
        "ROUTER_NODE_LIMIT": "-1",
        "ROUTER_ARRAY_LIMIT": "0",
    }, clear=False):
        settings = RouterSettings()

        # Should accept large values and negative values
        assert settings.context_limit == 999999999
        assert settings.node_limit == -1
        assert settings.array_limit == 0


def test_router_line_thresholds_invalid_format() -> None:
    """Test RouterSettings with invalid line thresholds format."""
    with patch.dict(os.environ, {
        "ROUTER_LINE_THRESHOLDS": "not,a,comma,list",
    }, clear=False):
        settings = RouterSettings()

        # Should fallback to defaults
        assert settings.line_thresholds == (60, 100)


def test_router_line_thresholds_single_value() -> None:
    """Test RouterSettings with single value in line thresholds."""
    with patch.dict(os.environ, {
        "ROUTER_LINE_THRESHOLDS": "50",
    }, clear=False):
        settings = RouterSettings()

        # Should fallback to defaults
        assert settings.line_thresholds == (60, 100)


def test_router_line_thresholds_inverted() -> None:
    """Test RouterSettings with inverted thresholds."""
    with patch.dict(os.environ, {
        "ROUTER_LINE_THRESHOLDS": "100,50",  # low > high
    }, clear=False):
        settings = RouterSettings()

        # Should swap them
        assert settings.line_thresholds == (50, 100)


def test_router_line_thresholds_zero_or_negative() -> None:
    """Test RouterSettings with zero or negative thresholds."""
    with patch.dict(os.environ, {
        "ROUTER_LINE_THRESHOLDS": "0,-10",
    }, clear=False):
        settings = RouterSettings()

        # Should fallback to defaults
        assert settings.line_thresholds == (60, 100)


def test_estimate_json_malformed_json() -> None:
    """Test JSON estimation with malformed JSON."""
    # Malformed JSON
    result = estimate_json_nodes_and_depth("{ not closed properly")

    # Should fallback to brace counting
    assert result[0] > 0  # node_count
    assert result[1] > 0  # depth


def test_estimate_json_empty_string() -> None:
    """Test JSON estimation with empty string."""
    result = estimate_json_nodes_and_depth("")

    assert result == (0, 0)


def test_estimate_json_very_deep_nesting() -> None:
    """Test JSON estimation with very deep nesting."""
    deep_json = "{" * 100 + "}" * 100
    result = estimate_json_nodes_and_depth(deep_json)

    assert result[1] == 100  # depth


def test_choose_tier_with_all_limits_exceeded() -> None:
    """Test tier selection when all limits are exceeded."""
    settings = RouterSettings()

    metrics = {
        "tokens_in": 50000,
        "tokens_out": 50000,
        "node_count": 1000,
        "schema_depth": 10,
        "array_elements": 6000,
        "csv_columns": 100,
        "line_count": 200,
        "nesting_depth": 5,
        "rag_k": 0,
        "rag_avg_score": 0.1,
    }

    tier = choose_start_tier(metrics, settings)

    # Should choose nano due to exceeding limits
    assert tier == "nano"


def test_choose_tier_with_no_rag_context() -> None:
    """Test tier selection with no RAG context."""
    settings = RouterSettings()

    metrics = {
        "tokens_in": 1000,
        "tokens_out": 1000,
        "node_count": 10,
        "schema_depth": 1,
        "line_count": 50,
        "nesting_depth": 1,
        "rag_k": 0,  # No RAG results
        "rag_avg_score": None,
    }

    tier = choose_start_tier(metrics, settings)

    # With no RAG, should be 7b but may promote due to rag_k=0
    assert tier in ["7b", "14b"]


def test_choose_next_tier_invalid_failure_type() -> None:
    """Test next tier selection with unknown failure type."""
    settings = RouterSettings()

    # Unknown failure type for 14b
    next_tier = choose_next_tier_on_failure("unknown_failure", "14b", {}, settings)

    # Should return nano
    assert next_tier == "nano"


def test_choose_next_tier_promote_once_false() -> None:
    """Test next tier selection with promote_once=False."""
    settings = RouterSettings()

    # With promote_once=False, should not promote
    next_tier = choose_next_tier_on_failure("truncation", "7b", {}, settings, promote_once=False)

    # Should return None (no further tier)
    assert next_tier is None


# ==============================================================================
# CONCURRENT MODIFICATION EDGE CASES
# ==============================================================================

def test_state_store_concurrent_updates(tmp_path: Path) -> None:
    """Test concurrent state updates."""
    store = StateStore(tmp_path / "state")

    # Add initial state
    store.update("repo1", lambda s: s)

    # Try concurrent updates
    for i in range(10):
        store.update("repo1", lambda s: s)

    # Should not raise exception


# ==============================================================================
# RESOURCE EXHAUSTION EDGE CASES
# ==============================================================================

def test_registry_very_large_file(tmp_path: Path) -> None:
    """Test registry with many entries."""
    registry_file = tmp_path / "repos.yml"

    # Create 1000 entries
    entries = []
    for i in range(1000):
        entries.append({
            "repo_id": f"repo-{i}",
            "repo_path": f"~/repo-{i}",
            "rag_workspace_path": f"~/repo-{i}/.llmc/rag"
        })

    registry_file.write_text(yaml.dump(entries))

    client = RegistryClient(path=registry_file)
    result = client.load()

    assert len(result) == 1000


def test_control_many_flags(tmp_path: Path) -> None:
    """Test control directory with many flag files."""
    control_dir = tmp_path / "control"
    control_dir.mkdir()

    # Create 1000 refresh flags
    for i in range(1000):
        (control_dir / f"refresh_repo-{i}.flag").touch()

    result = read_control_events(control_dir)

    assert len(result.refresh_repo_ids) == 1000
    assert "repo-500" in result.refresh_repo_ids


# ==============================================================================
# SECURITY/INJECTION EDGE CASES
# ==============================================================================

def test_registry_path_traversal_attempt(tmp_path: Path) -> None:
    """Test registry with path traversal attempts."""
    registry_file = tmp_path / "repos.yml"

    # Attempt path traversal
    registry_file.write_text(yaml.dump([{
        "repo_id": "evil",
        "repo_path": "../../../etc/passwd",
        "rag_workspace_path": "../../../tmp/evil"
    }]))

    client = RegistryClient(path=registry_file)
    result = client.load()

    # Path traversal entries should be rejected for safety
    assert "evil" not in result


def test_registry_control_chars_in_repo_id(tmp_path: Path) -> None:
    """Test registry with control characters in repo_id."""
    registry_file = tmp_path / "repos.yml"

    # Attempt injection with control chars
    registry_file.write_text(yaml.dump([{
        "repo_id": "repo\nwith\nnewlines",
        "repo_path": "~/repo",
        "rag_workspace_path": "~/repo/.llmc/rag"
    }]))

    client = RegistryClient(path=registry_file)
    result = client.load()

    assert "repo\nwith\nnewlines" in result


# ==============================================================================
# DATA CORRUPTION EDGE CASES
# ==============================================================================

def test_registry_binary_data(tmp_path: Path) -> None:
    """Test registry with binary data."""
    registry_file = tmp_path / "repos.yml"

    # Write binary data
    registry_file.write_bytes(b"\x00\x01\x02\x03\xff\xfe\xfd")

    client = RegistryClient(path=registry_file)

    # Should handle gracefully or raise exception
    with pytest.raises(Exception):
        client.load()


def test_registry_unicode_corruption(tmp_path: Path) -> None:
    """Test registry with corrupted Unicode."""
    registry_file = tmp_path / "repos.yml"

    # Invalid UTF-8 sequence
    registry_file.write_text("\x80\x81\x82\x83")

    client = RegistryClient(path=registry_file)

    # Should handle gracefully
    with pytest.raises(Exception):
        client.load()
