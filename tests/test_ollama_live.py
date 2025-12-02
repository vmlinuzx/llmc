
from pathlib import Path

import pytest

from tools.rag.database import Database
from tools.rag.embedding_manager import EmbeddingManager, EmbeddingProfileConfig

# We use the IP from llmc.toml
OLLAMA_URL = "http://192.168.5.20:11434"
TEST_DB_PATH = Path(".rag/test_ollama_live.db")

@pytest.fixture
def clean_db():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    db = Database(TEST_DB_PATH)
    yield db
    db.close()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

@pytest.mark.allow_network
def test_ollama_live_roundtrip(clean_db):
    """Live integration test with the Ollama server."""
    
    # Verify connectivity first (skip if offline)
    import requests
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code != 200:
            pytest.skip(f"Ollama server reachable but returned error: {resp.status_code}")
    except Exception as e:
        print(f"\nConnection error: {e}")
        pytest.skip(f"Ollama server unreachable: {e}")

    profiles = {
        "live_docs": EmbeddingProfileConfig(
            name="live_docs",
            raw={
                "provider": "ollama",
                "model": "nomic-embed-text:latest",
                "dimension": 768,
                "ollama": {
                    "api_base": OLLAMA_URL
                }
            }
        )
    }
    
    manager = EmbeddingManager(profiles, default_profile="live_docs")
    
    text = "The quick brown fox jumps over the lazy dog."
    
    # 1. Embed
    print(f"Requesting embedding from {OLLAMA_URL}...")
    vectors = manager.embed_passages([text], profile="live_docs")
    
    assert len(vectors) == 1
    vec = vectors[0]
    print(f"Received vector of length {len(vec)}")
    
    # Nomic should be 768
    assert len(vec) == 768
    
    # 2. Store
    clean_db.conn.execute("INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                          ("fox.txt", "txt", "hash_fox", len(text), 123.0))
    file_id = clean_db.conn.execute("SELECT id FROM files").fetchone()[0]
    
    span_hash = "span_fox_1"
    clean_db.conn.execute("""
        INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (file_id, "root", "text", 1, 1, 0, len(text), span_hash))
    
    clean_db.ensure_embedding_meta("nomic-embed-text:latest", 768, "live_docs")
    clean_db.store_embedding(span_hash, vec, "live_docs")
    
    # 3. Retrieve & Verify
    rows = list(clean_db.iter_embeddings("live_docs"))
    assert len(rows) == 1
    stored_vec_blob = rows[0]["vec"]
    
    import struct
    stored_vec = list(struct.unpack(f"<{768}f", stored_vec_blob))
    
    # Check fidelity
    # (Floating point transit via JSON might introduce tiny noise, 
    # but struct.pack/unpack is deterministic. The gap is only if Ollama returns different precision)
    assert len(stored_vec) == 768
    assert abs(stored_vec[0] - vec[0]) < 1e-6

