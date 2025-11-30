#!/usr/bin/env python3
"""Analytics Screen - Tool Envelope telemetry visualization."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Grid
from textual.screen import Screen
from textual.widgets import DataTable, Static, Header, Footer, Button

class AnalyticsScreen(Screen):
    """Dashboard for TE telemetry analytics."""

    CSS = """
    AnalyticsScreen {
        layout: vertical;
        padding: 1 1;
        background: $surface;
    }

    #header {
        height: 3;
        border: heavy $primary;
        content-align: center middle;
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }

    #dashboard-grid {
        layout: grid;
        grid-size: 2 2;  /* 2 columns, 2 rows */
        grid-columns: 1fr 1fr;
        grid-rows: auto 1fr;
        grid-gutter: 1;
        height: 1fr;
    }

    .panel {
        border: heavy $secondary;
        padding: 1 2;
        background: $boost;
        height: 100%;
    }

    .panel-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
        text-align: center;
    }

    #summary-panel {
        column-span: 2;
        height: auto;
        min-height: 10;
    }
    
    #summary-stats {
        height: 5;
        margin-top: 1;
        background: $surface;
    }

    #candidates-panel {
        height: 100%;
    }

    #enriched-panel {
        height: 100%;
    }

    DataTable {
        height: 1fr;
        border: solid $secondary;
    }
    
    .stat-item {
        width: 1fr;
        height: 4;
        content-align: center middle;
        padding: 0;
    }
    
    .stat-value {
        text-style: bold;
        color: $primary;
        text-align: center;
    }
    
    .stat-label {
        color: $text-muted;
        text-align: center;
    }
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("r", "refresh_data", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        """Create the analytics layout."""
        
        
        yield Static("TE Analytics Dashboard", id="header")

        with Grid(id="dashboard-grid"):
            # Row 1: Summary Stats (spans both columns)
            with Container(id="summary-panel", classes="panel"):
                yield Static("System Summary (Last 7 Days)", classes="panel-title")
                with Grid(id="summary-stats"):
                    # Pre-allocate 5 stat slots to avoid mount churn
                    for i in range(5):
                        with Container(classes="stat-item"):
                            yield Static("-", id=f"stat-val-{i}", classes="stat-value", markup=False)
                            yield Static("...", id=f"stat-lbl-{i}", classes="stat-label", markup=False)

            # Row 2, Col 1: Candidates
            with Container(id="candidates-panel", classes="panel"):
                yield Static("Top Unenriched Candidates (Unmatched)", classes="panel-title")
                yield DataTable(id="candidates-table", zebra_stripes=True)

            # Row 2, Col 2: Enriched Actions
            with Container(id="enriched-panel", classes="panel"):
                yield Static("Top Enriched Actions (Matched)", classes="panel-title")
                yield DataTable(id="enriched-table", zebra_stripes=True)

        yield Static("[r] Refresh   [esc] Back", id="footer")

    def on_mount(self) -> None:
        """Load data when screen is shown."""
        # Set grid columns for the stats
        self.query_one("#summary-stats", Grid).styles.grid_size_columns = 5
        self._setup_tables()
        self.refresh_data()

    def _setup_tables(self) -> None:
        """Initialize table columns."""
        cand_table = self.query_one("#candidates-table", DataTable)
        cand_table.add_columns("Command", "Calls", "Avg Size")
        
        enrich_table = self.query_one("#enriched-table", DataTable)
        enrich_table.add_columns("Command", "Calls", "Avg Latency")

    def _get_db_connection(self) -> sqlite3.Connection | None:
        """Get connection to telemetry DB."""
        # Resolve repo root relative to this file
        # llmc/tui/screens/analytics.py -> .../src/llmc
        repo_root = Path(__file__).resolve().parents[3]
        db_path = repo_root / ".llmc" / "te_telemetry.db"
        
        if not db_path.exists():
            return None
            
        try:
            return sqlite3.connect(db_path)
        except Exception:
            return None

    def refresh_data(self) -> None:
        """Fetch fresh data from DB and update widgets."""
        conn = self._get_db_connection()
        if not conn:
            self.query_one("#header", Static).update("TE Analytics (No Data Found)")
            return

        try:
            self._update_summary(conn)
            self._update_candidates(conn)
            self._update_enriched(conn)
            self.query_one("#header", Static).update(f"TE Analytics :: {datetime.now().strftime('%H:%M:%S')}")
        except Exception as exc:
            self.query_one("#header", Static).update(f"Error: {exc}")
        finally:
            conn.close()

    def _update_summary(self, conn: sqlite3.Connection) -> None:
        """Update the summary stats grid."""
        cursor = conn.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT cmd) as unique_cmds,
                AVG(latency_ms) as avg_lat,
                SUM(CASE WHEN mode = 'enriched' THEN 1 ELSE 0 END) as enriched,
                SUM(output_size) as total_bytes
            FROM telemetry_events
            WHERE timestamp >= datetime('now', '-7 days')
        """)
        row = cursor.fetchone()
        total, unique_cmds, avg_lat, enriched, total_bytes = row or (0, 0, 0, 0, 0)
        
        # Calculate percentages/formatting
        enrich_pct = (enriched / total * 100) if total else 0.0
        avg_lat_str = f"{avg_lat:.1f}ms" if avg_lat else "0ms"
        total_mb = (total_bytes or 0) / 1024 / 1024
        
        # Define stats to show
        stats = [
            ("Total Calls", f"{total:,}"),
            ("Unique Cmds", f"{unique_cmds}"),
            ("Enriched", f"{enrich_pct:.1f}%"),
            ("Avg Latency", avg_lat_str),
            ("Data Flow", f"{total_mb:.2f} MB"),
        ]
        
        # Update existing widgets by ID
        for i, (label, value) in enumerate(stats):
            self.query_one(f"#stat-val-{i}", Static).update(value)
            self.query_one(f"#stat-lbl-{i}", Static).update(label)

    def _update_candidates(self, conn: sqlite3.Connection) -> None:
        """Populate unenriched candidates table."""
        table = self.query_one("#candidates-table", DataTable)
        table.clear()
        
        cursor = conn.execute("""
            SELECT 
                cmd,
                COUNT(*) as count,
                AVG(output_size) as avg_output
            FROM telemetry_events 
            WHERE mode = 'passthrough'
            GROUP BY cmd 
            ORDER BY count DESC
            LIMIT 50
        """)
        
        for cmd, count, avg_out in cursor.fetchall():
            avg_kb = f"{avg_out/1024:.1f} KB"
            table.add_row(Text(cmd), str(count), avg_kb)

    def _update_enriched(self, conn: sqlite3.Connection) -> None:
        """Populate enriched actions table."""
        table = self.query_one("#enriched-table", DataTable)
        table.clear()
        
        cursor = conn.execute("""
            SELECT 
                cmd,
                COUNT(*) as count,
                AVG(latency_ms) as avg_lat
            FROM telemetry_events 
            WHERE mode = 'enriched'
            GROUP BY cmd 
            ORDER BY count DESC
            LIMIT 50
        """)
        
        for cmd, count, avg_lat in cursor.fetchall():
            avg_str = f"{avg_lat:.1f}ms"
            table.add_row(Text(cmd), str(count), avg_str)

    def action_refresh_data(self) -> None:
        """Action handler for 'r' key."""
        self.refresh_data()
