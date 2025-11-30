import pytest
from pathlib import Path
import sqlite3
from tools.rag.indexer import index_repo
from tools.rag.database import Database
from tools.rag.workers import execute_embeddings, execute_enrichment
from tools.rag.types import SpanRecord

def test_routing_integration(tmp_path, monkeypatch):
    # Setup repo
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    
    # Create files
    (repo_root / "code.py").write_text("def foo(): pass")
    (repo_root / "doc.md").write_text("# Doc")
    
    # Config
    (repo_root / "llmc.toml").write_text("""
[embeddings]
default_profile = "docs"

[embeddings.profiles.code_jina]
provider = "ignored"
model = "hash-emb-v1"
dim = 64
capabilities = ["code"]

[embeddings.profiles.docs]
provider = "ignored"
model = "hash-emb-v1"
dim = 64

[embeddings.routes.code]
profile = "code_jina"
index = "emb_code"

[embeddings.routes.docs]
profile = "docs"
index = "embeddings"

[routing.slice_type_to_route]
code = "code"
docs = "docs"
""")
    
    monkeypatch.chdir(repo_root)
    
    # Index
    index_repo()
    
    db_path = repo_root / ".rag" / "index_v2.db"
    db = Database(db_path)
    
    # Check spans classification
    row_code = db.conn.execute("SELECT slice_type, slice_language FROM spans WHERE file_id = (SELECT id FROM files WHERE path='code.py')").fetchone()
    assert row_code["slice_type"] == "code"
    assert row_code["slice_language"] == "python"
    
    row_doc = db.conn.execute("SELECT slice_type FROM spans WHERE file_id = (SELECT id FROM files WHERE path='doc.md')").fetchone()
    assert row_doc["slice_type"] == "docs"

    # Embeddings
    execute_embeddings(db, repo_root)
    
    # Check where embeddings went
    # Code -> emb_code
    code_emb = db.conn.execute("SELECT * FROM emb_code").fetchall()
    assert len(code_emb) > 0
    assert code_emb[0]["route_name"] == "code"
    assert code_emb[0]["profile_name"] == "code_jina"
    
    # Docs -> embeddings
    docs_emb = db.conn.execute("SELECT * FROM embeddings").fetchall()
    assert len(docs_emb) > 0
    assert docs_emb[0]["route_name"] == "docs"
    
    # Enrichment
    def mock_llm(prompt):
        return {
             "summary_120w": "summary",
             "inputs": [],
             "outputs": [],
             "side_effects": [],
             "pitfalls": [],
             "usage_snippet": None,
             "evidence": [],
             "tags": []
        }
        
    execute_enrichment(db, repo_root, mock_llm)
    
    # Check enrichment metadata
    # Filter by span hash from code file (using spans table to join or select)
    code_span_hash = code_emb[0]["span_hash"]
    enrich_code = db.conn.execute("SELECT content_type, content_language FROM enrichments WHERE span_hash = ?", (code_span_hash,)).fetchone()
    
    assert enrich_code["content_type"] == "code"
    assert enrich_code["content_language"] == "python"
