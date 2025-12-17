import sqlite3

from llmc_mcp.config import McpObservabilityConfig
from llmc_mcp.observability import ObservabilityContext


def test_sqlite_telemetry(tmp_path):
    db_path = tmp_path / "telemetry.db"
    config = McpObservabilityConfig(
        enabled=True, sqlite_enabled=True, sqlite_path=str(db_path)
    )

    obs = ObservabilityContext(config)

    # Record some events
    obs.record("cid1", "tool_a", 100.0, True)
    obs.record("cid2", "tool_b", 200.0, False)
    obs.record("cid3", "tool_a", 150.0, True)

    # Verify DB content
    assert db_path.exists()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Check total count
        cursor.execute("SELECT COUNT(*) FROM tool_usage")
        assert cursor.fetchone()[0] == 3

        # Check tool_a count
        cursor.execute("SELECT COUNT(*) FROM tool_usage WHERE tool = 'tool_a'")
        assert cursor.fetchone()[0] == 2

        # Check failures
        cursor.execute("SELECT COUNT(*) FROM tool_usage WHERE success = 0")
        assert cursor.fetchone()[0] == 1

        # Check details
        cursor.execute(
            "SELECT tool, latency_ms, correlation_id FROM tool_usage WHERE correlation_id = 'cid1'"
        )
        row = cursor.fetchone()
        assert row == ("tool_a", 100.0, "cid1")


if __name__ == "__main__":
    pass
