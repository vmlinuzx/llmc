import json
from pathlib import Path

from tools.rag_daemon.state_store import StateStore
from tools.rag_daemon.models import RepoState


def test_state_store_round_trip_tmpdir(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    state = RepoState(
        repo_id="repo-123",
        last_run_status="success",
    )
    store.upsert(state)

    loaded_all = store.load_all()
    assert "repo-123" in loaded_all
    loaded = loaded_all["repo-123"]
    assert loaded.repo_id == "repo-123"
    assert loaded.last_run_status == "success"


def test_state_store_atomic_write(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    state = RepoState(repo_id="repo-atomic")

    store.upsert(state)
    state_file = tmp_path / "repo-atomic.json"
    assert state_file.exists()

    raw = json.loads(state_file.read_text(encoding="utf-8"))
    assert raw["repo_id"] == "repo-atomic"
