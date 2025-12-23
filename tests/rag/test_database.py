import sqlite3
from pathlib import Path
from llmc.rag.database import check_and_migrate_all_repos, Database, DB_SCHEMA_VERSION

def test_check_and_migrate_all_repos_empty():
    assert check_and_migrate_all_repos([]) == {}

def test_check_and_migrate_all_repos_skips_missing(tmp_path):
    # Repo exists but no DB
    repo = tmp_path / "repo"
    repo.mkdir()
    
    results = check_and_migrate_all_repos([str(repo)])
    assert results == {}

def test_check_and_migrate_all_repos_returns_version(tmp_path):
    repo = tmp_path / "repo"
    db_dir = repo / ".llmc" / "rag"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "index_v2.db"
    
    # Create a dummy DB with version 0
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA user_version = 0")
    conn.close()
    
    results = check_and_migrate_all_repos([str(repo)])
    
    assert str(repo) in results
    assert results[str(repo)] == DB_SCHEMA_VERSION
    
    # Verify DB was actually migrated
    conn = sqlite3.connect(str(db_path))
    ver = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()
    assert ver == DB_SCHEMA_VERSION

from unittest.mock import patch

def test_check_and_migrate_all_repos_exception(tmp_path):
    repo = tmp_path / "repo"
    db_dir = repo / ".llmc" / "rag"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "index_v2.db"
    # Ensure file exists so the check passes
    db_path.touch()

    with patch("llmc.rag.database.Database") as MockDB:
        MockDB.side_effect = Exception("Boom")
        results = check_and_migrate_all_repos([str(repo)])
        assert results[str(repo)] == -1
