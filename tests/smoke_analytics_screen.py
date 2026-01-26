from pathlib import Path
import sqlite3
import sys

# Add src/llmc to pythonpath so we can import the module
sys.path.append("/home/vmlinux/src/llmc")

try:
    from textual.app import App

    from llmc.tui.screens.analytics import AnalyticsScreen
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    sys.exit(1)

print("Successfully imported AnalyticsScreen")

# Create a dummy DB if it doesn't exist to test query logic
db_path = Path("/home/vmlinux/src/llmc/.llmc/te_telemetry.db")
if not db_path.exists():
    print("Creating dummy DB for test...")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS telemetry_events (timestamp TEXT, cmd TEXT, mode TEXT, output_size INTEGER, latency_ms REAL, agent_id TEXT)"
    )
    conn.execute(
        "INSERT INTO telemetry_events VALUES (datetime('now'), 'ls', 'passthrough', 100, 10.0, 'test')"
    )
    conn.commit()
    conn.close()


class TestApp(App):
    def on_mount(self):
        screen = AnalyticsScreen()
        self.push_screen(screen)
        print("Screen pushed")

        # Manually trigger the refresh logic to see if it crashes
        try:
            # We can't easily simulate the full mount lifecycle in a headless script without running the loop
            # But we can check if the methods exist and run in isolation if we mock things,
            # or just rely on the fact that we imported it and the DB logic is valid SQL.

            # Let's try to connect to DB using the screen's helper
            conn = screen._get_db_connection()
            if conn:
                print("DB Connection successful")
                screen._update_summary(conn)
                print("_update_summary ok")
                screen._update_candidates(conn)
                print("_update_candidates ok")
                screen._update_enriched(conn)
                print("_update_enriched ok")
                conn.close()
            else:
                print("Could not connect to DB")

        except Exception as e:
            print(f"LOGIC ERROR: {e}")
            sys.exit(1)

        print("Smoke test passed")
        sys.exit(0)


if __name__ == "__main__":
    # We can't actually run the app in this environment usually, but let's try the import and basic logic checks
    # Just instantiating the screen is a good first step.
    screen = AnalyticsScreen()
    print("Screen instantiated")

    # Check DB logic directly
    conn = screen._get_db_connection()
    if conn:
        try:
            cursor = conn.execute("SELECT count(*) FROM telemetry_events")
            print(f"DB has {cursor.fetchone()[0]} rows")
        except Exception as e:
            print(f"DB Query failed: {e}")

    print("Test complete")
