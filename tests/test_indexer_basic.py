"""
Basic tests for the RAG indexer.
"""

from __future__ import annotations

import os
from pathlib import Path

from tools.rag import indexer
from tools.rag.utils import find_repo_root


def _write_simple_python_file(repo_root: Path) -> Path:
    """Create a simple Python source file in the repo."""
    src = repo_root / "sample.py"
    src.write_text(
        "def hello(name: str) -> str:\n"
        "    return f'hello {name}'\n",
        encoding="utf-8",
    )
    return src


def test_index_repo_creates_db_and_spans_export(tmp_path: Path, monkeypatch) -> None:
    """index_repo on a minimal repo produces DB and spans export."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    _write_simple_python_file(repo_root)

    # Run indexing with CWD set to the temporary repo.
    monkeypatch.chdir(repo_root)

    stats = indexer.index_repo(export_json=True)
    assert stats.files == 1
    assert stats.spans > 0
    assert stats["duration_sec"] >= 0.0

    resolved_root = find_repo_root(repo_root)
    db_path = indexer.db_path(resolved_root)
    spans_path = indexer.spans_export_path(resolved_root)

    assert db_path.exists()
    assert spans_path.exists()
    # Export should contain at least one JSON line.
    assert spans_path.read_text(encoding="utf-8").strip() != ""


def test_index_repo_skips_unchanged_files(tmp_path: Path, monkeypatch) -> None:
    """Second index_repo run should count unchanged file rather than reindexing."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    _write_simple_python_file(repo_root)

    monkeypatch.chdir(repo_root)

    first = indexer.index_repo(export_json=False)
    assert first.files == 1
    assert first.spans > 0

    second = indexer.index_repo(export_json=False)
    assert second.files == 0
    # The unchanged counter should reflect the one file we indexed previously.
    assert second.unchanged == 1

