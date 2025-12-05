
from scripts.migrate_fts5_no_stopwords import migrate_fts5_index
from tools.rag.database import Database


def test_fts5_migration(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".rag").mkdir(parents=True)
    
    db_path = repo_root / ".rag" / "index_v2.db"
    
    # 1. Create DB and fake data
    db = Database(db_path)
    
    # Create necessary tables for rebuild_enrichments_fts
    db.conn.execute("INSERT INTO files (path, lang, file_hash, size, mtime) VALUES ('f1', 'py', 'h1', 10, 0)")
    file_id = db.conn.execute("SELECT id FROM files").fetchone()[0]
    db.conn.execute(f"INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash) VALUES ({file_id}, 'sym1', 'func', 1, 1, 0, 10, 'sh1')")
    db.conn.execute("INSERT INTO enrichments (span_hash, summary, model) VALUES ('sh1', 'This is a model for the system', 'm1')")
    
    db.conn.commit()
    db.close()
    
    # 2. Run migration
    migrate_fts5_index(repo_root)
    
    # 3. Verify
    db = Database(db_path)
    
    # Check if we can search for "model"
    # Note: 'model' is allegedly a stopword in some configurations (though typically not standard Porter)
    # 'the' IS a standard stopword.
    
    # If stopwords are ACTIVE (bad), searching for "the" might fail or be ignored.
    # If stopwords are GONE (good), "the" should match.
    
    cursor = db.conn.execute("SELECT * FROM enrichments_fts WHERE enrichments_fts MATCH 'the'")
    results = cursor.fetchall()
    assert len(results) > 0, "Should find 'the' if stopwords are disabled"
    
    cursor = db.conn.execute("SELECT * FROM enrichments_fts WHERE enrichments_fts MATCH 'model'")
    results = cursor.fetchall()
    assert len(results) > 0, "Should find 'model'"

    # Verify table definition
    cursor = db.conn.execute("SELECT sql FROM sqlite_master WHERE name='enrichments_fts'")
    sql = cursor.fetchone()[0]
    assert "tokenize='unicode61'" in sql or 'tokenize="unicode61"' in sql

    db.close()
