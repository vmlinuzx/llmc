"""Unit tests for enrichment-aware Database helpers.

These tests exercise the span/enrichment join helpers and the optional
FTS-backed search surface introduced in the enrichment integration work.

They intentionally operate on an isolated, temporary SQLite index so they
do not depend on any real repository data or long-running pipelines.
"""

from __future__ import annotations

from pathlib import Path
import time

from tools.rag.database import Database


def _seed_simple_index(db_path: Path) -> Database:
    """Create a tiny index with one file/span/enrichment row."""
    db = Database(db_path)

    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO files(path, lang, file_hash, size, mtime)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("foo.py", "python", "hash", 10, time.time()),
        )
        file_id = conn.execute("SELECT id FROM files WHERE path = ?", ("foo.py",)).fetchone()[0]

        conn.execute(
            """
            INSERT INTO spans(
                file_id, symbol, kind, start_line, end_line,
                byte_start, byte_end, span_hash, doc_hint
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (file_id, "foo.bar", "function", 1, 5, 0, 10, "span1", None),
        )

        conn.execute(
            """
            INSERT INTO enrichments(
                span_hash, summary, tags, evidence, model,
                created_at, schema_ver, inputs, outputs,
                side_effects, pitfalls, usage_snippet
            ) VALUES (?, ?, ?, ?, ?, strftime('%s','now'), ?, ?, ?, ?, ?, ?)
            """,
            ("span1", "test summary", None, "[]", "test-model", "1", "[]", "[]", "[]", "[]", None),
        )

    return db


def test_fetch_all_spans_and_enrichments(tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    db = _seed_simple_index(db_path)

    spans = db.fetch_all_spans()
    enrichments = db.fetch_all_enrichments()

    assert len(spans) == 1
    assert spans[0].symbol == "foo.bar"
    assert len(enrichments) == 1
    assert enrichments[0].symbol == "foo.bar"
    assert enrichments[0].summary == "test summary"

    db.close()


def test_search_enrichments_fts(tmp_path: Path) -> None:
    db_path = tmp_path / "index.db"
    db = _seed_simple_index(db_path)

    # Rebuild the FTS index from the current data
    count = db.rebuild_enrichments_fts()

    # When FTS is unavailable (older SQLite builds), the helper should
    # degrade gracefully and return zero rows.
    results = db.search_enrichments_fts("test")

    if not db.fts_available:
        assert count == 0
        assert results == []
    else:
        assert count >= 1
        assert len(results) >= 1
        symbol, summary, score = results[0]
        assert symbol == "foo.bar"
        assert summary is None or "test summary" in summary
        # score may be None when bm25() is not available, but the tuple
        # should still unpack cleanly.

    db.close()
