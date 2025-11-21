import importlib
import json
from pathlib import Path

import pytest

import tools.rag.service as service_module


@pytest.fixture
def service_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("LLMC_RAG_SERVICE_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("LLMC_RAG_FAILURE_DB", str(tmp_path / "failures.db"))
    importlib.invalidate_caches()
    module = importlib.reload(service_module)
    yield module


def test_service_state_add_remove_repo_persists(service_mod, tmp_path):
    state = service_mod.ServiceState()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    added = state.add_repo(str(repo_path))
    assert added is True
    assert repo_path.resolve().as_posix() in state.state["repos"]

    state.remove_repo(str(repo_path))
    assert repo_path.resolve().as_posix() not in state.state["repos"]

    # Ensure file persisted the removal
    persisted = json.loads(service_mod.STATE_FILE.read_text())
    assert repo_path.resolve().as_posix() not in persisted["repos"]


def test_failure_tracker_threshold(service_mod, tmp_path):
    tracker = service_mod.FailureTracker()
    span = "span-123"
    repo = str(tmp_path / "repo")

    for attempt in range(service_mod.MAX_FAILURES - 1):
        tracker.record_failure(span, repo, f"attempt {attempt}")
        assert tracker.is_failed(span, repo) is False

    tracker.record_failure(span, repo, "final attempt")
    assert tracker.is_failed(span, repo) is True

    tracker.conn.close()
