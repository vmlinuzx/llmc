
from pathlib import Path
import sqlite3

from llmc.rag.database import Database
from llmc.rag.types import SpanRecord


def test_fresh_db_has_all_phase1_columns(tmp_path):
    """AC-1.1: Fresh DB created from SCHEMA has all new columns."""
    db_path = tmp_path / "fresh_p1.db"
    db = Database(db_path)
    conn = sqlite3.connect(str(db_path))
    
    def check_col(table, col):
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        assert any(r[1] == col for r in rows), f"Column {col} missing from {table}"

    # files
    check_col("files", "sidecar_path")
    
    # spans
    check_col("spans", "imports")
    check_col("spans", "slice_type")
    
    # embeddings
    check_col("embeddings", "route_name")
    
    # enrichments
    check_col("enrichments", "inputs")
    check_col("enrichments", "tokens_per_second")
    check_col("enrichments", "content_type")
    
    # file_descriptions
    check_col("file_descriptions", "input_hash")
    
    conn.close()
    db.close()

def test_imports_persistence_roundtrip(tmp_path):
    """AC-1.2, AC-1.3: Span imports are persisted and loaded correctly."""
    db_path = tmp_path / "imports.db"
    db = Database(db_path)
    
    # Create file record first
    import time

    from llmc.rag.types import FileRecord
    f_rec = FileRecord(
        path=Path("src/foo.py"),
        lang="python",
        file_hash="abc",
        size=100,
        mtime=time.time()
    )
    fid = db.upsert_file(f_rec)
    
    # Create span with imports
    span = SpanRecord(
        file_path=Path("src/foo.py"),
        lang="python",
        symbol="Foo",
        kind="class",
        start_line=1,
        end_line=10,
        byte_start=0,
        byte_end=100,
        span_hash="span1",
        imports=["os", "sys", "json"]
    )
    
    # Insert
    db.replace_spans(fid, [span])
    
    # Fetch by hash
    loaded = db.get_span_by_hash("span1")
    assert loaded is not None
    assert loaded.imports == ["os", "sys", "json"]
    
    # Fetch all
    all_spans = db.fetch_all_spans()
    assert len(all_spans) == 1
    assert all_spans[0].imports == ["os", "sys", "json"]
    
    db.close()
