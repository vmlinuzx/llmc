import importlib
import json
import time
from unittest.mock import patch

import pytest

import llmc.rag.service as service_module
from llmc.rag.service import RAGService


@pytest.fixture
def service_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("LLMC_RAG_SERVICE_STATE", str(tmp_path / "state.json"))
    monkeypatch.setenv("LLMC_RAG_FAILURE_DB", str(tmp_path / "failures.db"))
    importlib.invalidate_caches()
    module = importlib.reload(service_module)
    yield module


def test_service_state_vacuum_tracking(service_mod, tmp_path):
    state = service_mod.ServiceState()
    repo_path = str(tmp_path / "repo")

    # Default should be 0.0
    assert state.get_last_vacuum(repo_path) == 0.0

    # Update
    state.update_last_vacuum(repo_path)
    last = state.get_last_vacuum(repo_path)
    assert last > 0.0
    assert time.time() - last < 5.0  # Recently updated

    # Persistence
    persisted = json.loads(service_mod.STATE_FILE.read_text())
    assert repo_path in persisted["last_vacuum"]
    assert persisted["last_vacuum"][repo_path] == last


def test_process_repo_runs_vacuum(service_mod, tmp_path):
    state = service_mod.ServiceState()
    tracker = service_mod.FailureTracker()
    service = RAGService(state, tracker)

    repo = tmp_path / "test_repo"
    repo.mkdir()

    # Mock modules to avoid real work
    with (
        patch("llmc.rag.service.get_vacuum_interval_hours", return_value=1),
        patch("llmc.rag.service.Database") as MockDB,
        patch("llmc.rag.service.index_path_for_write", return_value=repo / "index.db"),
        patch("llmc.rag.runner.detect_changes", return_value=[]),
        patch("llmc.rag.runner.run_enrich"),
        patch("llmc.rag.runner.run_embed"),
        patch("llmc.rag.doctor.run_rag_doctor"),
        patch("llmc.rag.quality.run_quality_check"),
        patch("llmc.rag_nav.tool_handlers.build_graph_for_repo"),
        patch("time.sleep"),
    ):
        # Case 1: Never run -> Should run
        service.process_repo(str(repo))
        assert MockDB.return_value.vacuum.called
        last_vacuum = state.get_last_vacuum(str(repo))
        assert last_vacuum > 0.0

        MockDB.reset_mock()

        # Case 2: Just run -> Should not run
        service.process_repo(str(repo))
        assert not MockDB.return_value.vacuum.called

        # Case 3: Force time travel -> Should run
        # Manually set last vacuum to 2 hours ago
        state.state["last_vacuum"][str(repo)] = time.time() - 7200
        service.process_repo(str(repo))
        assert MockDB.return_value.vacuum.called
