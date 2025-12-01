import pytest
import sqlite3
import struct
from pathlib import Path
from tools.rag.embedding_manager import EmbeddingManager, EmbeddingProfileConfig
from tools.rag.database import Database

DB_PATH = Path(".rag/test_integrity.db")

@pytest.fixture
def fresh_db():
    if DB_PATH.exists():
        DB_PATH.unlink()
    
    db = Database(DB_PATH)
    
    # Seed some files and spans so we can link embeddings
    db.conn.execute("INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                    ("test.py", "python", "hash1", 100, 12345.0))
    file_id = db.conn.execute("SELECT id FROM files").fetchone()[0]
    
    db.conn.execute("""
        INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (file_id, "func1", "function", 1, 10, 0, 100, "span1"))
    
    db.conn.execute("""
        INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (file_id, "func2", "function", 11, 20, 101, 200, "span2"))
    
    db.conn.commit()
    yield db
    db.close()
    if DB_PATH.exists():
        DB_PATH.unlink()

def test_profile_isolation(fresh_db):
    """Ensure embeddings for different profiles are stored separately."""
    
    # Config with multiple profiles using Hash provider for determinism
    profiles = {
        "code": EmbeddingProfileConfig(name="code", raw={"provider": "hash", "dimension": 64}),
        "docs": EmbeddingProfileConfig(name="docs", raw={"provider": "hash", "dimension": 128})
    }
    
    manager = EmbeddingManager(profiles, default_profile="code")
    
    # 1. Generate embeddings for 'code' profile
    vec_code = manager.embed_passages(["def func1(): pass"], profile="code")[0]
    assert len(vec_code) == 64
    fresh_db.ensure_embedding_meta("hash-model", 64, "code")
    fresh_db.store_embedding("span1", vec_code, profile_name="code")
    
    # 2. Generate embeddings for 'docs' profile
    vec_docs = manager.embed_passages(["Documentation for func1"], profile="docs")[0]
    assert len(vec_docs) == 128
    fresh_db.ensure_embedding_meta("hash-model", 128, "docs")
    fresh_db.store_embedding("span2", vec_docs, profile_name="docs")
    
    # 3. Direct DB Inspection
    rows = fresh_db.conn.execute("SELECT span_hash, profile_name, length(vec) FROM embeddings WHERE span_hash IN ('span1', 'span2')").fetchall()
    
    data = {row[0]: (row[1], row[2]) for row in rows}
    assert "span1" in data
    assert "span2" in data
    
    assert data["span1"][0] == "code"
    assert data["span2"][0] == "docs"
    
    # Float is 4 bytes, so length should be dim * 4
    assert data["span1"][1] == 64 * 4
    assert data["span2"][1] == 128 * 4

def test_vector_integrity(fresh_db):
    """Verify stored binary blobs decode back to correct floats."""
    
    profiles = {
        "test": EmbeddingProfileConfig(name="test", raw={"provider": "hash", "dimension": 4})
    }
    manager = EmbeddingManager(profiles, default_profile="test")
    
    # Generate a known vector
    original_vec = manager.embed_passages(["integrity check"], profile="test")[0]
    
    fresh_db.ensure_embedding_meta("hash", 4, "test")
    fresh_db.store_embedding("span2", original_vec, "test")
    
    # Read back raw blob
    blob = fresh_db.conn.execute("SELECT vec FROM embeddings WHERE span_hash='span2'").fetchone()[0]
    
    # Decode manually
    decoded_vec = list(struct.unpack(f"<{len(original_vec)}f", blob))
    
    # Compare with tolerance
    for v1, v2 in zip(original_vec, decoded_vec):
        assert abs(v1 - v2) < 1e-6

def test_profile_metadata(fresh_db):
    """Check embeddings_meta table population."""
    fresh_db.ensure_embedding_meta("model-A", 100, "profile-A")
    fresh_db.ensure_embedding_meta("model-B", 200, "profile-B")
    
    rows = fresh_db.conn.execute("SELECT profile, model, dim FROM embeddings_meta ORDER BY profile").fetchall()
    
    assert len(rows) == 2
    assert rows[0][0] == "profile-A"
    assert rows[0][1] == "model-A"
    assert rows[0][2] == 100
    
    assert rows[1][0] == "profile-B"
    assert rows[1][1] == "model-B"
    assert rows[1][2] == 200