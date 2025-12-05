
import sqlite3

import pytest

from tools.rag.db_fts import RagDbNotFound, _column_map, _detect_fts_table, _open_db


def test_open_db_not_found(tmp_path):
    with pytest.raises(RagDbNotFound):
        _open_db(tmp_path)

def test_detect_fts_table_no_table(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    # Create a normal table, not FTS
    conn.execute("CREATE TABLE normal (id INTEGER, text TEXT)")
    
    with pytest.raises(RuntimeError, match="No FTS virtual table detected"):
        _detect_fts_table(conn)
    conn.close()

def test_detect_fts_table_success(tmp_path):
    db_path = tmp_path / "test_fts.db"
    conn = sqlite3.connect(str(db_path))
    # Create FTS table
    conn.execute("CREATE VIRTUAL TABLE spans USING fts5(path, text)")
    
    table = _detect_fts_table(conn)
    assert table == "spans"
    conn.close()

def test_column_map_success(tmp_path):
    db_path = tmp_path / "test_cols.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE VIRTUAL TABLE spans USING fts5(path, text, start_line, end_line)")
    
    cols = _column_map(conn, "spans")
    assert cols["path"] == "path"
    assert cols["text"] == "text"
    assert cols["start"] == "start_line"
    assert cols["end"] == "end_line"
    conn.close()

def test_column_map_aliases(tmp_path):
    db_path = tmp_path / "test_aliases.db"
    conn = sqlite3.connect(str(db_path))
    # Use aliases
    conn.execute("CREATE VIRTUAL TABLE chunks USING fts5(file, content, lineno, lineno_end)")
    
    cols = _column_map(conn, "chunks")
    assert cols["path"] == "file"
    assert cols["text"] == "content"
    assert cols["start"] == "lineno"
    assert cols["end"] == "lineno_end"
    conn.close()

def test_column_map_missing_required(tmp_path):
    db_path = tmp_path / "test_missing.db"
    conn = sqlite3.connect(str(db_path))
    # Missing 'path' equivalent
    conn.execute("CREATE VIRTUAL TABLE broken USING fts5(text, start_line)")
    
    with pytest.raises(RuntimeError, match="Required column not found"):
        _column_map(conn, "broken")
    conn.close()
