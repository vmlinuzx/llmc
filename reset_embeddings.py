import sqlite3
from pathlib import Path

db_path = Path(".rag/index_v2.db")
if db_path.exists():
    conn = sqlite3.connect(db_path)
    # Delete all rows from embeddings to simulate "pending" state
    conn.execute("DELETE FROM embeddings")
    conn.commit()
    print("Deleted all embeddings. Index should now show pending items.")
    conn.close()
else:
    print("DB not found.")
