from io import StringIO
from pathlib import Path
import sqlite3
import sys
from unittest.mock import patch

import pytest

# Assuming the main function is in llmc.te.cli
# We need to adjust the path to import it
sys.path.insert(0, str(Path(__file__).parents[2]))

from llmc.te.cli import _handle_stats


@pytest.fixture
def temp_db_path(tmp_path):
    """Fixture to create a temporary database path."""
    db_dir = tmp_path / ".llmc"
    db_dir.mkdir()
    return db_dir / "te_telemetry.db"


@pytest.fixture
def setup_mock_db(temp_db_path):
    """
    Fixture to set up a mock SQLite database with sample data
    and patch sqlite3.connect.
    """
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry_events (
            timestamp TEXT,
            cmd TEXT,
            mode TEXT,
            input_size INTEGER,
            output_size INTEGER,
            truncated BOOLEAN,
            handle_created BOOLEAN,
            latency_ms REAL,
            error TEXT,
            output_text TEXT
        )
    """)

    # Insert sample data
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2025-12-01T10:00:00Z", "ls -l", "passthrough", 10, 100, 0, 0, 50.0, None, "output"),
    )
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2025-12-01T10:01:00Z", "grep pattern", "passthrough", 15, 80, 0, 0, 75.0, None, "output"),
    )
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2025-12-01T10:02:00Z", "grep other", "enriched", 20, 120, 0, 0, 100.0, None, "output"),
    )
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2025-12-01T10:03:00Z", "ls -a", "passthrough", 8, 90, 0, 0, 60.0, None, "output"),
    )
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2025-12-01T10:04:00Z", "cat file.txt", "enriched", 12, 110, 0, 0, 90.0, None, "output"),
    )
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2025-12-01T10:05:00Z", "grep pattern", "passthrough", 15, 85, 0, 0, 70.0, None, "output"),
    )
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2025-12-01T10:06:00Z", "grep pattern", "enriched", 20, 125, 0, 0, 110.0, None, "output"),
    )
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2025-12-01T10:07:00Z", "grep pattern", "enriched", 20, 130, 0, 0, 105.0, None, "output"),
    )
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2025-12-01T10:08:00Z", "find .", "passthrough", 5, 200, 0, 0, 200.0, None, "output"),
    )
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("2025-12-01T10:09:00Z", "grep other", "enriched", 20, 115, 0, 0, 95.0, None, "output"),
    )

    # Routing events
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "2025-12-01T10:10:00Z",
            "[routing_ingest_slice] slice_type=code, route_name=code, profile_name=code_jina",
            "routing_ingest_slice",
            0,
            0,
            0,
            0,
            10.0,
            None,
            "",
        ),
    )
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "2025-12-01T10:11:00Z",
            "[routing_ingest_slice] slice_type=docs, route_name=docs, profile_name=docs_text",
            "routing_ingest_slice",
            0,
            0,
            0,
            0,
            12.0,
            None,
            "",
        ),
    )
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "2025-12-01T10:12:00Z",
            "[routing_ingest_slice] slice_type=code, route_name=code, profile_name=code_jina",
            "routing_ingest_slice",
            0,
            0,
            0,
            0,
            11.0,
            None,
            "",
        ),
    )
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "2025-12-01T10:13:00Z",
            "[routing_query_classify] route_name=code, confidence=0.8",
            "routing_query_classify",
            0,
            0,
            0,
            0,
            5.0,
            None,
            "",
        ),
    )
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "2025-12-01T10:14:00Z",
            "[routing_query_classify] route_name=docs, confidence=0.9",
            "routing_query_classify",
            0,
            0,
            0,
            0,
            6.0,
            None,
            "",
        ),
    )
    cursor.execute(
        "INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "2025-12-01T10:15:00Z",
            "[routing_fallback] type=missing_slice_type_mapping, slice_type=weird_type, fallback_to=docs",
            "routing_fallback",
            0,
            0,
            0,
            0,
            3.0,
            None,
            "",
        ),
    )

    conn.commit()
    conn.close()

    # Patch sqlite3.connect to return a connection to our temporary database
    with patch("sqlite3.connect", return_value=sqlite3.connect(temp_db_path)) as mock_connect:
        yield mock_connect  # Yield control to the test function


class TestTeStatsOutput:
    """Tests the output format of te --stats."""

    @patch("sys.stdout", new_callable=StringIO)
    @patch("llmc.te.cli._find_repo_root")
    def test_stats_output_format(
        self, mock_find_repo_root, mock_stdout, temp_db_path, setup_mock_db
    ):
        """
        Tests that the _handle_stats function produces output
        in the expected format with the correct sections.
        """
        mock_find_repo_root.return_value = temp_db_path.parent.parent

        # Execute the function
        _handle_stats(mock_find_repo_root.return_value)

        output = mock_stdout.getvalue()

        expected_output = """┌─ [TE] Telemetry Summary ──────────────────────────────┐          
│ Total calls:     16                                   │          
│ Unique commands: 11                                   │          
│ Avg latency:     62.6ms                               │          
│ Total output:    1.1 KB                               │          
└───────────────────────────────────────────────────────┘          
                                                                   
┌─ Top 5 Unenriched Calls ──────────────────────────────┐          
│ grep pattern (2x) - 72.5ms                            │          
│ [routing_ingest_slice] slice_type=code, route_name=code, profile_name=code_jina (2x) - 10.5ms│                                      
│ ls -l (1x) - 50.0ms                                   │          
│ ls -a (1x) - 60.0ms                                   │          
│ find . (1x) - 200.0ms                                 │          
└───────────────────────────────────────────────────────┘          
                                                                   
┌─ Top 5 Enriched Calls ────────────────────────────────┐          
│ grep pattern (2x) - 107.5ms                           │          
│ grep other (2x) - 97.5ms                              │          
│ cat file.txt (1x) - 90.0ms                            │          
└───────────────────────────────────────────────────────┘          
                                                                   
┌─ Routing Stats ───────────────────────────────────────┐          
│ Slices Ingested:                                      │          
│   by_slice_type:                                      │          
│     code            2                           │                
│     docs            1                           │                
│   by_route_name:                                      │          
│     code            2                           │                
│     docs            1                           │                
│                                                       │          
│ Query Routing:                                        │          
│   by_route_name:                                      │          
│     code            1                           │                
│     docs            1                           │                
│   Fallbacks:                                          │          
│     missing_slice_type_mapping 1                           │     
│   Errors:                                             │          
└───────────────────────────────────────────────────────┘"""
        expected_output_lines = [
            line.strip() for line in expected_output.splitlines() if line.strip()
        ]
        actual_output_lines = [line.strip() for line in output.splitlines() if line.strip()]

        # Compare line by line for clearer diffs
        assert len(actual_output_lines) == len(expected_output_lines)
        for i, (actual_line, expected_line) in enumerate(
            zip(actual_output_lines, expected_output_lines)
        ):
            assert actual_line == expected_line, (
                f"Line {i + 1} differs: Actual='{actual_line}', Expected='{expected_line}'"
            )

    @patch("sys.stdout", new_callable=StringIO)
    @patch("llmc.te.cli._find_repo_root")
    def test_stats_no_data(self, mock_find_repo_root, mock_stdout, tmp_path):
        """
        Tests that _handle_stats gracefully handles cases with no telemetry data.
        """
        db_dir = tmp_path / ".llmc"
        db_dir.mkdir()
        empty_db_path = db_dir / "te_telemetry.db"

        # Create an empty DB
        conn = sqlite3.connect(empty_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telemetry_events (
                timestamp TEXT,
                cmd TEXT,
                mode TEXT,
                input_size INTEGER,
                output_size INTEGER,
                truncated BOOLEAN,
                handle_created BOOLEAN,
                latency_ms REAL,
                error TEXT,
                output_text TEXT
            )
        """)
        conn.commit()
        conn.close()

        mock_find_repo_root.return_value = empty_db_path.parent.parent

        with patch("sqlite3.connect", return_value=sqlite3.connect(empty_db_path)):
            _handle_stats(mock_find_repo_root.return_value)

        output = mock_stdout.getvalue()

        assert "┌─ [TE] Telemetry Summary ──────────────────────────────┐" in output
        assert "Total calls:     0" in output
        assert "Unique commands: 0" in output
        assert "Avg latency:     0.0ms" in output
        assert "Total output:    0.0 KB" in output

        assert "┌─ Top 5 Unenriched Calls ──────────────────────────────┐" in output
        assert "│ (no data)" in output

        assert "┌─ Top 5 Enriched Calls ────────────────────────────────┐" in output
        assert "│ (no data)" in output

        assert "┌─ Routing Stats ───────────────────────────────────────┐" in output
        assert "│ Slices Ingested:                                      │" in output
        assert "│   (no data)                                           │" in output
        assert "│ Query Routing:                                        │" in output
        assert "│   (no data)                                           │" in output
        assert "└───────────────────────────────────────────────────────┘" in output
