import sqlite3
from pathlib import Path

db_path = Path(".rag/index_v2.db")
if not db_path.exists():
    print("DB not found")
else:
    conn = sqlite3.connect(db_path)
    try:
        res = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='embeddings_meta'").fetchone()
        if res:
            print(res[0])
        else:
            print("Table embeddings_meta not found")
    except Exception as e:
        print(e)
