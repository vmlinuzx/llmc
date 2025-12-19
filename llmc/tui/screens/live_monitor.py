#!/usr/bin/env python3
"""Live Monitor Screen - Real-time TE telemetry feed, Matrix-style."""

from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import DataTable, Static

# Agent color mapping
AGENT_COLORS = {
    "claude-dc": "cyan",
    "codex-cli": "green",
    "manual-dave": "yellow",
    "minimax-cli": "magenta",
    "gpt-chat": "blue",
}
DEFAULT_AGENT_COLOR = "white"


class LiveMonitorScreen(Screen):
    """Real-time TE command feed with auto-refresh."""

    CSS = """
    LiveMonitorScreen {
        layout: vertical;
        padding: 1 1;
        background: $surface;
    }

    #header-bar {
        layout: horizontal;
        height: 3;
        border: heavy $primary;
        padding: 0 2;
        background: $boost;
    }

    #title {
        width: 1fr;
        content-align: left middle;
        text-style: bold;
    }

    #live-indicator {
        width: auto;
        content-align: right middle;
        color: $success;
        text-style: bold;
    }

    #feed-table {
        height: 1fr;
        border: heavy $secondary;
        background: $surface;
    }

    #detail-panel {
        height: 14;
        border: heavy $accent;
        background: $boost;
        padding: 1 2;
        overflow-y: auto;
    }

    #detail-title {
        text-style: bold;
        color: $accent;
    }

    #detail-content {
        height: 1fr;
        color: $text;
    }

    #stats-bar {
        height: 3;
        border: heavy $secondary;
        content-align: center middle;
        background: $boost;
        margin-top: 1;
    }

    #footer-help {
        height: 1;
        content-align: center middle;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("p", "toggle_pause", "Pause/Resume"),
        ("c", "clear_feed", "Clear"),
        ("r", "force_refresh", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._paused = False
        self._last_id: int = 0
        self._total_calls: int = 0
        self._agents_seen: set = set()
        self._total_latency: float = 0.0
        self._enriched_count: int = 0
        self._refresh_timer: Timer | None = None
        self._row_data: dict[str, dict[str, Any]] = {}  # row_key -> full event data
        self._max_rows: int = 100

    def compose(self) -> ComposeResult:
        """Create the live monitor layout."""
        with Container(id="header-bar"):
            yield Static("TE Live Monitor", id="title")
            yield Static("● LIVE", id="live-indicator")

        yield DataTable(id="feed-table", zebra_stripes=True, cursor_type="row")

        with ScrollableContainer(id="detail-panel"):
            yield Static("Event Details", id="detail-title")
            yield Static("[dim]Select a row to view details[/dim]", id="detail-content")

        yield Static("Waiting for data...", id="stats-bar")
        yield Static(
            "[p] Pause  [c] Clear  [r] Refresh  [↑↓] Select  [esc] Back",
            id="footer-help",
        )

    def on_mount(self) -> None:
        """Start the refresh timer on mount."""
        self._setup_table()
        self._load_initial_history()
        self._update_stats()
        self._refresh_timer = self.set_interval(1.5, self._poll_new_events)

    def _setup_table(self) -> None:
        """Initialize the data table columns."""
        table = self.query_one("#feed-table", DataTable)
        table.add_columns("Time", "Agent", "Mode", "Latency", "Size", "Cmd", "Args")
        # Make command column expand
        table.cursor_type = "row"

    def on_unmount(self) -> None:
        """Clean up timer on unmount."""
        if self._refresh_timer:
            self._refresh_timer.stop()

    def _get_db_connection(self) -> sqlite3.Connection | None:
        """Get connection to telemetry DB."""
        repo_root = Path(__file__).resolve().parents[3]
        db_path = repo_root / ".llmc" / "te_telemetry.db"
        if not db_path.exists():
            return None
        try:
            return sqlite3.connect(db_path)
        except Exception:
            return None

    def _load_initial_history(self) -> None:
        """Load last 50 events on startup."""
        conn = self._get_db_connection()
        if not conn:
            return
        try:
            cursor = conn.execute(
                """
                SELECT id, timestamp, agent_id, session_id, cmd, mode, 
                       input_size, output_size, truncated, latency_ms, error, output_text
                FROM telemetry_events
                ORDER BY id DESC
                LIMIT 50
            """
            )
            rows = cursor.fetchall()
            for row in reversed(rows):
                self._add_row(row)
        finally:
            conn.close()

    def _poll_new_events(self) -> None:
        """Poll for new events since last check."""
        if self._paused:
            return
        conn = self._get_db_connection()
        if not conn:
            return
        try:
            cursor = conn.execute(
                """
                SELECT id, timestamp, agent_id, session_id, cmd, mode,
                       input_size, output_size, truncated, latency_ms, error, output_text
                FROM telemetry_events
                WHERE id > ?
                ORDER BY id ASC
            """,
                (self._last_id,),
            )
            new_rows = cursor.fetchall()
            if new_rows:
                for row in new_rows:
                    self._add_row(row)
                self._update_stats()
                self._pulse_indicator()
        finally:
            conn.close()

    def _add_row(self, row: tuple) -> None:
        """Add a telemetry row to the table."""
        (
            row_id,
            timestamp,
            agent_id,
            session_id,
            cmd,
            mode,
            input_size,
            output_size,
            truncated,
            latency_ms,
            error,
            output_text,
        ) = row

        # Update tracking
        self._last_id = max(self._last_id, row_id)
        self._total_calls += 1
        self._total_latency += latency_ms or 0
        if agent_id:
            self._agents_seen.add(agent_id)
        if mode == "enriched":
            self._enriched_count += 1

        # Store full data for detail view
        row_key = f"row_{row_id}"
        self._row_data[row_key] = {
            "id": row_id,
            "timestamp": timestamp,
            "agent_id": agent_id,
            "session_id": session_id,
            "cmd": cmd,
            "mode": mode,
            "input_size": input_size,
            "output_size": output_size,
            "truncated": bool(truncated),
            "latency_ms": latency_ms,
            "error": error,
            "output_text": output_text,
        }

        # Format timestamp
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            time_str = dt.strftime("%H:%M:%S.%f")[:-3]
        except Exception:
            time_str = timestamp[:12] if timestamp else "??:??:??"

        # Format agent with color
        agent_str = (agent_id or "unknown")[:12]
        agent_color = AGENT_COLORS.get(agent_id, DEFAULT_AGENT_COLOR)
        agent_text = Text(agent_str, style=agent_color)

        # Format mode
        if mode == "enriched":
            mode_text = Text("enr", style="green bold")
        else:
            mode_text = Text("pass", style="dim")

        # Format latency
        if latency_ms and latency_ms >= 1000:
            lat_str = f"{latency_ms / 1000:.1f}s"
        else:
            lat_str = f"{latency_ms or 0:.0f}ms"

        # Format size
        size_kb = (output_size or 0) / 1024
        size_str = f"{size_kb:.1f}KB"

        # Split command into base cmd and args
        cmd_full = cmd or "?"
        cmd_parts = cmd_full.split(None, 1)  # Split on first whitespace
        cmd_base = cmd_parts[0] if cmd_parts else "?"
        cmd_args = cmd_parts[1] if len(cmd_parts) > 1 else ""

        # Add to table
        table = self.query_one("#feed-table", DataTable)
        table.add_row(
            time_str,
            agent_text,
            mode_text,
            lat_str,
            size_str,
            cmd_base,
            cmd_args,
            key=row_key,
        )

        # Trim old rows if needed
        while table.row_count > self._max_rows:
            first_key = list(self._row_data.keys())[0]
            table.remove_row(first_key)
            del self._row_data[first_key]

        # Auto-scroll to bottom
        table.scroll_end(animate=False)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection - show details."""
        if event.row_key is None:
            return
        row_key = str(event.row_key.value)
        self._show_detail(row_key)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Handle row highlight (cursor move) - show details."""
        if event.row_key is None:
            return
        row_key = str(event.row_key.value)
        self._show_detail(row_key)

    def _show_detail(self, row_key: str) -> None:
        """Display detail panel for selected row."""
        data = self._row_data.get(row_key)
        if not data:
            return

        # Format the detail view
        lines = []

        # Command (full, prominent)
        lines.append(f"[bold cyan]Command:[/bold cyan] {data['cmd']}")
        lines.append("")

        # Metadata grid
        mode_style = "green" if data["mode"] == "enriched" else "dim"
        lines.append(
            f"[bold]Agent:[/bold] {data['agent_id']}  │  "
            f"[bold]Mode:[/bold] [{mode_style}]{data['mode']}[/{mode_style}]  │  "
            f"[bold]Latency:[/bold] {data['latency_ms']}ms"
        )

        in_kb = (data["input_size"] or 0) / 1024
        out_kb = (data["output_size"] or 0) / 1024
        trunc_str = "[yellow]Yes[/yellow]" if data["truncated"] else "[green]No[/green]"
        lines.append(
            f"[bold]Input:[/bold] {in_kb:.2f}KB  │  "
            f"[bold]Output:[/bold] {out_kb:.2f}KB  │  "
            f"[bold]Truncated:[/bold] {trunc_str}"
        )

        lines.append(
            f"[bold]Session:[/bold] {data['session_id']}  │  [bold]ID:[/bold] {data['id']}"
        )
        lines.append(f"[bold]Timestamp:[/bold] {data['timestamp']}")

        # Error if present
        if data["error"]:
            lines.append(f"[bold red]Error:[/bold red] {data['error']}")

        # Output if captured
        if data.get("output_text"):
            lines.append("")
            lines.append("[bold cyan]─── Output ───[/bold cyan]")
            # Show output, truncated display if very long
            output = data["output_text"]
            if len(output) > 2000:
                output = (
                    output[:2000]
                    + f"\n[dim]... ({len(data['output_text'])} bytes total)[/dim]"
                )
            lines.append(output)
        else:
            lines.append("")
            lines.append("[dim]Output capture disabled. Enable in llmc.toml:[/dim]")
            lines.append("[dim][tool_envelope.telemetry][/dim]")
            lines.append("[dim]capture_output = true[/dim]")

        detail_content = self.query_one("#detail-content", Static)
        detail_content.update("\n".join(lines))

    def _update_stats(self) -> None:
        """Update the stats bar."""
        avg_lat = self._total_latency / self._total_calls if self._total_calls else 0
        enr_pct = (
            (self._enriched_count / self._total_calls * 100) if self._total_calls else 0
        )

        filled = int(enr_pct / 10)
        bar = "█" * filled + "░" * (10 - filled)

        stats = (
            f"Session: {self._total_calls} calls │ "
            f"{len(self._agents_seen)} agents │ "
            f"{avg_lat:.0f}ms avg │ "
            f"[green]{bar}[/green] {enr_pct:.0f}% enriched"
        )
        self.query_one("#stats-bar", Static).update(stats)

    def _pulse_indicator(self) -> None:
        """Briefly change indicator to show activity."""
        indicator = self.query_one("#live-indicator", Static)
        indicator.update("[bold green]● LIVE[/bold green]")

    def action_toggle_pause(self) -> None:
        """Toggle pause/resume of live feed."""
        self._paused = not self._paused
        indicator = self.query_one("#live-indicator", Static)
        if self._paused:
            indicator.update("[yellow]⏸ PAUSED[/yellow]")
        else:
            indicator.update("[green]● LIVE[/green]")

    def action_clear_feed(self) -> None:
        """Clear the feed display and reset stats."""
        table = self.query_one("#feed-table", DataTable)
        table.clear()
        self._row_data.clear()
        self._total_calls = 0
        self._agents_seen.clear()
        self._total_latency = 0.0
        self._enriched_count = 0
        self._update_stats()
        self.query_one("#detail-content", Static).update(
            "[dim]Select a row to view details[/dim]"
        )

    def action_force_refresh(self) -> None:
        """Force an immediate poll."""
        was_paused = self._paused
        self._paused = False
        self._poll_new_events()
        self._paused = was_paused
    def action_go_back(self) -> None:
        """Go back to dashboard if nothing to pop."""
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            from llmc.tui.screens.dashboard import DashboardScreen
            self.app.switch_screen(DashboardScreen())

