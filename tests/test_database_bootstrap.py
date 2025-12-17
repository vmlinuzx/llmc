from llmc.rag.database import Database
from llmc.rag.inspector import _fetch_enrichment


def test_database_recovers_from_corrupt_file(tmp_path):
    """Database should quarantine corrupt files and recreate a clean DB."""
    db_path = tmp_path / "index_v2.db"
    db_path.write_text("not a real database")

    db = Database(db_path)
    try:
        db.conn.execute("SELECT name FROM sqlite_master").fetchall()
    finally:
        db.close()

    backups = list(tmp_path.glob("index_v2.db.corrupt.*"))
    assert backups, "Corrupt DB should be quarantined"


def test_fetch_enrichment_handles_corrupt_db(tmp_path):
    """Inspector enrichment lookup should survive corrupt databases."""
    db_path = tmp_path / "index_v2.db"
    db_path.write_text("totally invalid sqlite data")

    result = _fetch_enrichment(db_path, span_hash="abc123")

    backups = list(tmp_path.glob("index_v2.db.corrupt.*"))
    assert backups, "Corrupt DB should be quarantined during inspector lookup"
    assert result["summary"] is None
