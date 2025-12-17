from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from llmc.rag_nav.metadata import load_status, save_status, status_path
from llmc.rag_nav.models import IndexStatus


def test_load_status_missing_returns_none(tmp_path: Path) -> None:
    repo_root = tmp_path
    assert load_status(repo_root) is None


def test_load_status_corrupt_returns_none(tmp_path: Path) -> None:
    repo_root = tmp_path
    status_file = status_path(repo_root)
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text("{not: valid json", encoding="utf-8")

    assert load_status(repo_root) is None


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    repo_root = tmp_path
    status = IndexStatus(
        repo=str(repo_root),
        index_state="fresh",
        last_indexed_at="2025-01-01T00:00:00Z",
        last_indexed_commit="abc123",
        schema_version="1",
        last_error=None,
    )

    path = save_status(repo_root, status)
    assert path == status_path(repo_root)
    assert path.exists()

    loaded = load_status(repo_root)
    assert loaded == status
