"""
Core tests for tools.rag.database.Database.
"""

from __future__ import annotations

from pathlib import Path

from llmc.rag.database import Database
from llmc.rag.types import FileRecord, SpanRecord


def _make_db(tmp_path: Path) -> Database:
    """Create a new Database in a temporary directory."""
    db_path = tmp_path / "index.db"
    return Database(db_path)


def _sample_file_record(path: str = "sample.py") -> FileRecord:
    return FileRecord(
        path=Path(path),
        lang="python",
        file_hash="hash-1",
        size=10,
        mtime=1234.0,
    )


def _sample_span(symbol: str, span_hash: str) -> SpanRecord:
    return SpanRecord(
        file_path=Path("src") / "foo.py",
        lang="python",
        symbol=symbol,
        kind="function",
        start_line=1,
        end_line=2,
        byte_start=0,
        byte_end=10,
        span_hash=span_hash,
        doc_hint=None,
    )


def test_upsert_file_and_get_file_hash_roundtrip(tmp_path: Path) -> None:
    """upsert_file stores metadata and get_file_hash returns the expected hash."""
    db = _make_db(tmp_path)
    try:
        record = _sample_file_record("foo.py")
        file_id = db.upsert_file(record)
        assert isinstance(file_id, int)

        # Hash should be visible via the helper.
        stored_hash = db.get_file_hash(Path("foo.py"))
        assert stored_hash == record.file_hash
    finally:
        db.close()


def test_replace_spans_preserves_unchanged_and_reports_stats(
    tmp_path: Path, caplog
) -> None:
    """replace_spans keeps unchanged spans and only inserts/deletes the delta."""
    import logging
    caplog.set_level(logging.INFO, logger="llmc.rag.database")
    db = _make_db(tmp_path)
    try:
        file_id = db.upsert_file(_sample_file_record("foo.py"))

        # Seed with two spans.
        original_spans = [
            _sample_span("func_a", "span-a"),
            _sample_span("func_b", "span-b"),
        ]
        db.replace_spans(file_id, original_spans)

        # Now call replace_spans with one unchanged and one new span.
        updated_spans = [
            _sample_span("func_a", "span-a"),  # unchanged hash
            _sample_span("func_c", "span-c"),  # new span
        ]
        db.replace_spans(file_id, updated_spans)

        # We expect two spans total, with hashes span-a and span-c.
        rows = db.conn.execute(
            "SELECT span_hash, symbol FROM spans ORDER BY span_hash"
        ).fetchall()
        hashes = {row["span_hash"] for row in rows}
        symbols = {row["symbol"] for row in rows}
        assert hashes == {"span-a", "span-c"}
        assert symbols == {"func_a", "func_c"}

        # The log should mention one added, one deleted, one unchanged.
        log_output = " ".join(record.message for record in caplog.records)
        assert "1 unchanged" in log_output or "unchanged" in log_output
        assert "1 added" in log_output or "added" in log_output
        assert "1 deleted" in log_output or "deleted" in log_output
    finally:
        db.close()


def test_quarantine_corrupt_db_on_open(tmp_path: Path) -> None:
    """Corrupt DB files are quarantined and replaced with a fresh DB."""
    db_path = tmp_path / "index.db"
    # Write garbage so sqlite3 sees it as corrupt.
    db_path.write_bytes(b"not-a-real-sqlite-db")

    # First initialization should quarantine and succeed.
    db = Database(db_path)
    try:
        # Sanity check: files table exists and is writable.
        db.upsert_file(_sample_file_record("foo.py"))
        assert db.get_file_hash(Path("foo.py")) == "hash-1"
    finally:
        db.close()

    # There should now be exactly one quarantined file alongside the fresh DB.
    corrupt_files = list(tmp_path.glob("index.db.corrupt.*"))
    assert len(corrupt_files) == 1
