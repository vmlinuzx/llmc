"""
Basic tests for tools.rag.db_fts FTS search.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3

from tools.rag.db_fts import FtsHit, RagDbNotFound, fts_search


def _make_fts_db(tmp_path: Path) -> Path:
    """Create a minimal FTS5 database compatible with db_fts expectations."""
    db_path = tmp_path / "index_v2.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE VIRTUAL TABLE spans USING fts5(path, start_line, end_line, text)")
        conn.executemany(
            "INSERT INTO spans(path, start_line, end_line, text) VALUES (?, ?, ?, ?)",
            [
                ("foo.py", 10, 12, "function foo does something"),
                ("bar.py", 20, 25, "bar helper for foo queries"),
            ],
        )
        conn.commit()
    finally:
        conn.close()
    # Place the DB under a .rag directory as db_fts expects.
    rag_dir = tmp_path / ".rag"
    rag_dir.mkdir(parents=True, exist_ok=True)
    dest = rag_dir / "index_v2.db"
    db_path.replace(dest)
    return dest


def test_fts_search_returns_hits(tmp_path: Path) -> None:
    """fts_search returns at least one matching hit with basic fields populated."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    _make_fts_db(repo_root)

    hits = fts_search(repo_root, "foo", limit=5)
    assert hits, "Expected at least one FTS hit for 'foo'"
    first = hits[0]
    assert isinstance(first, FtsHit)
    assert first.file.endswith(".py")
    assert first.start_line >= 1
    assert first.end_line >= first.start_line
    assert "foo" in first.text


def test_fts_search_raises_when_db_missing(tmp_path: Path) -> None:
    """fts_search raises RagDbNotFound if no DB candidates exist."""
    repo_root = tmp_path / "empty_repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    try:
        _ = fts_search(repo_root, "foo", limit=5)
    except RagDbNotFound:
        return
    assert False, "Expected RagDbNotFound when no RAG DB exists"
