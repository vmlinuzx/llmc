
import json
from pathlib import Path
import sqlite3
from unittest.mock import MagicMock

from llmc.rag.database import Database
from llmc.rag.graph_db import GraphDatabase, build_from_json


def test_graph_meta_exists(tmp_path):
    """AC-2.1: graph_meta table exists in schema."""
    db_path = tmp_path / "graph.db"
    _ = GraphDatabase(db_path)
    
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("PRAGMA table_info(graph_meta)").fetchall()
        cols = {row[1] for row in rows}
        assert "key" in cols
        assert "value" in cols

def test_nodes_have_span_hash_column(tmp_path):
    """AC-2.2: nodes table has span_hash column."""
    db_path = tmp_path / "graph.db"
    _ = GraphDatabase(db_path)
    
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("PRAGMA table_info(nodes)").fetchall()
        cols = {row[1] for row in rows}
        assert "span_hash" in cols

def test_span_hash_populated_from_metadata(tmp_path):
    """AC-2.3: span_hash is extracted from node metadata during build."""
    json_path = tmp_path / ".llmc" / "rag_graph.json"
    json_path.parent.mkdir(parents=True)
    
    graph_data = {
        "nodes": [
            {
                "id": "node1",
                "name": "Node1",
                "path": "src/file1.py",
                "metadata": {"span_hash": "hash_123"}
            },
            {
                "id": "node2",
                "name": "Node2",
                "path": "src/file2.py" 
                # Missing metadata/span_hash
            }
        ],
        "edges": []
    }
    json_path.write_text(json.dumps(graph_data))
    
    db = build_from_json(tmp_path)
    
    node1 = db.get_node("node1")
    assert node1.span_hash == "hash_123"
    
    node2 = db.get_node("node2")
    assert node2.span_hash is None

def test_graph_meta_written_on_build(tmp_path):
    """AC-2.4: graph_meta is populated with mtime and built_at."""
    # Mock the index DB behavior indirectly or verify what we can
    # Ideally build_from_json should take the index_db path or instance to read mtime?
    # The SDD says: "Store: index_db_mtime — max(mtime) from files table at build time"
    # BUT build_from_json signature in existing code is `build_from_json(repo_root: Path)`.
    # It assumes `.llmc/rag_graph.json` exists.
    # To get index_db mtime, it needs access to index_db.
    # If the signature doesn't change, it must open the default index db path.
    # Let's verify if build_from_json logic I implement actually does this.
    
    # Setup graph JSON
    json_path = tmp_path / ".llmc" / "rag_graph.json"
    json_path.parent.mkdir(parents=True)
    json_path.write_text(json.dumps({"nodes": [], "edges": []}))
    
    # Setup Index DB
    index_db_path = tmp_path / ".llmc" / "rag" / "index_v2.db"
    index_db_path.parent.mkdir(parents=True)
    
    # We need a real Database instance to write files table
    # We need to ensure we can import Database properly.
    # In tests/conftest.py or similar usually sets up path. 
    # Here we just use the class.
    
    idx_db = Database(index_db_path)
    # Insert a file with specific mtime
    from llmc.rag.types import FileRecord
    idx_db.upsert_file(FileRecord(
        path=Path("foo.py"),
        lang="py",
        file_hash="abc",
        size=10,
        mtime=12345.0
    ))
    idx_db.conn.commit()
    idx_db.close()    
    # Run build
    db = build_from_json(tmp_path)
    
    # Check meta
    with sqlite3.connect(db.path) as conn:
        rows = dict(conn.execute("SELECT key, value FROM graph_meta").fetchall())
        assert "index_db_mtime" in rows
        assert float(rows["index_db_mtime"]) == 12345.0
        assert "built_at" in rows

def test_staleness_detection(tmp_path):
    """AC-2.5: is_stale returns True when index is newer."""
    db_path = tmp_path / "graph.db"
    db = GraphDatabase(db_path)
    
    # Manually write old mtime to graph_meta
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO graph_meta (key, value) VALUES (?, ?)", 
                     ("index_db_mtime", "100.0"))
    
    # Mock index DB
    mock_idx = MagicMock()
    # Mock connection to return a newer mtime
    mock_conn = MagicMock()
    mock_idx.conn = mock_conn
    mock_conn.execute.return_value.fetchone.return_value = [200.0]
    
    assert db.is_stale(mock_idx) is True
    
    # Mock index DB with older/same mtime
    mock_conn.execute.return_value.fetchone.return_value = [100.0]
    assert db.is_stale(mock_idx) is False

