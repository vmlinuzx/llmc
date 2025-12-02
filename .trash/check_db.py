import sqlite3
from pathlib import Path

db_path = Path(".llmc/te_telemetry.db")
if db_path.exists():
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT cmd, count(*) as c FROM telemetry_events WHERE mode='passthrough' GROUP BY cmd ORDER BY c DESC")
    rows = cursor.fetchall()
    print(f"Total rows: {len(rows)}")
    for r in rows[:10]:
        print(r)
    conn.close()
else:
    print("DB not found")
