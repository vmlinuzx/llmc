#!/usr/bin/env python3
"""Monitor Screen - real-time system dashboard with analytics."""

from datetime import datetime
import os
from pathlib import Path
import random
import subprocess
import sys
import threading
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Grid, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Button, Static

from llmc.tui.screens.config import ConfigScreen
from tools.rag.analytics import QueryTracker


class MonitorScreen(Screen):
    """Live monitoring dashboard showing system stats and analytics."""

    CSS = """
    MonitorScreen {
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

    #main-grid {
        layout: grid;
        grid-size: 2 1;
        grid-columns: 42% 58%;
        grid-rows: 1fr;
        grid-gutter: 1;
        height: 1fr;
    }

    .panel {
        border: heavy $secondary;
        padding: 1 2;
        background: $boost;
    }

    .panel-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #left-column {
        layout: vertical;
        height: 1fr;
    }

    #menu-panel {
        height: 7fr; /* ~70% of the left column */
        margin-bottom: 1;
        background: $surface;
    }

    #context-panel {
        height: 3fr; /* ~30% of the left column */
        background: $surface;
    }

    #right-column {
        layout: vertical;
        height: 1fr;
    }

    #stats-panel {
        height: 2fr;
        margin-bottom: 1;
        background: $surface;
    }

    #log-panel {
        height: 3fr;
        background: $surface;
    }

    .menu-btn {
        width: 100%;
        margin: 0 0 1 0;
        text-align: left;
        border: solid $secondary;
    }

    .menu-btn:hover {
        border: heavy $accent;
        background: $boost;
    }

    #footer {
        height: 3;
        border: heavy $primary;
        content-align: center middle;
        margin-top: 1;
    }

    .metric-line {
        height: auto;
        margin: 0 0;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("escape", "app.pop_screen", "Back"),
        ("1", "nav_monitor", "Monitor"),
        ("2", "nav_search", "Search"),
        ("3", "nav_inspect", "Inspector"),
        ("4", "nav_config", "Config"),
        ("5", "nav_analytics", "Analytics"),
        ("6", "nav_live_monitor", "TE Live"),
        ("7", "nav_rag_doctor", "RAG Doctor"),
    ]

    def __init__(self):
        super().__init__()
        self.logs = []
        self._log_proc: subprocess.Popen | None = None
        self._log_thread: threading.Thread | None = None
        self._log_stream_error: bool = False
        self._max_log_lines: int = 200
        self.start_time = datetime.now()
        self.menu_items = [
            ("1", "Monitor System", self.action_nav_monitor),
            ("2", "Search Code", self.action_nav_search),
            ("3", "Code Inspector", self.action_nav_inspect),
            ("4", "Configuration", self.action_nav_config),
            ("5", "TE Analytics", self.action_nav_analytics),
            ("6", "TE Live Monitor", self.action_nav_live_monitor),
            ("7", "RAG Doctor", self.action_nav_rag_doctor),
        ]

    def compose(self) -> ComposeResult:
        """Create the monitor layout."""
        yield Static("LLMC Monitor", id="header")

        with Grid(id="main-grid"):
            with Container(id="left-column"):
                with Container(id="menu-panel", classes="panel"):
                    yield Static("Navigation", classes="panel-title")
                    with ScrollableContainer(id="menu-list"):
                        for key, label, _ in self.menu_items:
                            yield Button(f"[{key}] {label}", id=f"menu-{key}", classes="menu-btn")

                with Container(id="context-panel", classes="panel"):
                    yield Static("Context & Analytics", classes="panel-title")
                    yield Static(id="context-body")

            with Container(id="right-column"):
                with Container(id="stats-panel", classes="panel"):
                    yield Static("System Status", classes="panel-title")
                    yield Static(id="stats-body")

                with Container(id="log-panel", classes="panel"):
                    yield Static("Enrichment Log", classes="panel-title")
                    yield Static(id="log-output", markup=False)

        yield Static("[q] Quit   [r] Refresh   [esc] Back", id="footer")

    def on_mount(self) -> None:
        """Start timers when mounted."""
        self.query_one("#header", Static).update(f"LLMC Monitor :: repo {self.app.repo_root}")
        # Start log streaming from the RAG service (falls back to simulation if unavailable).
        self._start_log_stream()
        self.update_menu()
        self.update_stats()
        self.update_logs(force=True)
        self.update_context()

        self.set_interval(2.0, self.update_stats)
        self.set_interval(0.7, self.update_logs)
        self.set_interval(5.0, self.update_context)

    def on_unmount(self) -> None:
        """Clean up any background log processes."""
        self._stop_log_stream()

    def _start_log_stream(self) -> None:
        """Start background process to stream `llmc-rag-service logs -f` output."""
        if self._log_proc is not None or self._log_stream_error:
            return

        # Resolve the llmc repo root from this file location.
        repo_root = Path(__file__).resolve().parents[3]
        script_path = repo_root / "scripts" / "llmc-rag-service"

        try:
            if script_path.is_file() and os.access(script_path, os.X_OK):
                base_cmd = [str(script_path)]
            else:
                # Fallback to module invocation; behaviour should match the script wrapper.
                base_cmd = [sys.executable, "-m", "tools.rag.service"]

            cmd = base_cmd + ["logs", "-f", "-n", str(self._max_log_lines)]
            self._log_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as exc:
            self._log_stream_error = True
            # Fall back to simulated logs but surface the error in the log panel.
            self.add_log(f"Error starting enrichment log stream: {exc}", "ERR")
            return

        if self._log_proc.stdout is None:
            self._log_stream_error = True
            self.add_log(
                "Enrichment log stream has no stdout; using simulated logs.",
                "ERR",
            )
            return

        def _reader() -> None:
            """Background reader that mirrors `llmc-rag-service logs -f` output."""
            try:
                for raw_line in self._log_proc.stdout:  # type: ignore[union-attr]
                    line = raw_line.rstrip("\n")
                    if not line:
                        continue
                    self.logs.append(line)
                    if len(self.logs) > self._max_log_lines * 4:
                        self.logs = self.logs[-self._max_log_lines * 4 :]
            except Exception:
                self._log_stream_error = True
            finally:
                if self._log_proc is not None:
                    try:
                        self._log_proc.terminate()
                    except Exception:
                        try:
                            self._log_proc.kill()
                        except Exception:
                            pass
                    self._log_proc = None

        self._log_thread = threading.Thread(target=_reader, daemon=True)
        self._log_thread.start()

    def _stop_log_stream(self) -> None:
        """Stop background log process if running."""
        proc = self._log_proc
        self._log_proc = None
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    def update_menu(self) -> None:
        """Render the navigation menu block."""
        for key, label, _ in self.menu_items:
            btn = self.query_one(f"#menu-{key}", Button)
            btn.label = f"[{key}] {label}"

    def update_stats(self) -> None:
        """Fetch and display repo stats."""
        try:
            repo_root = self.app.repo_root
            stats = self.get_repo_stats(repo_root)

            status_color = "green" if stats.get("daemon_status") == "ONLINE" else "red"
            content = "\n".join(
                [
                    f"📂 Files Tracked: [bold green]{stats['files_tracked']:,}[/bold green]",
                    f"🧠 Graph Nodes: [bold green]{stats['graph_nodes']:,}[/bold green]",
                    f"🎫 Token Usage: [bold yellow]{stats['token_usage']:,}[/bold yellow]",
                    f"🔋 Daemon Status: [bold {status_color}]{stats['daemon_status']}[/bold {status_color}]",
                    f"⏱ Uptime: {str(datetime.now() - self.start_time).split('.')[0]}",
                ]
            )
            self.query_one("#stats-body", Static).update(content)
        except Exception as exc:
            self.add_log(f"Error updating stats: {exc}", "ERR")

    def update_logs(self, force: bool = False) -> None:
        """Refresh log output, preferring real RAG service logs."""
        # Try to start the real log stream lazily if it is not already active.
        if self._log_proc is None and not self._log_stream_error:
            self._start_log_stream()

        # If we have no logs yet and the stream is healthy, just show a placeholder.
        if not self.logs and not self._log_stream_error:
            self.query_one("#log-output", Static).update("Awaiting logs...")
            return

        # Fallback: if streaming failed entirely, reuse the old simulated behaviour.
        if self._log_stream_error and not self.logs:
            self._simulate_logs(force=force)

        log_text = "\n".join(self.logs[-self._max_log_lines :])
        self.query_one("#log-output", Static).update(log_text or "Awaiting logs...")
        self.query_one("#log-output", Static).markup = False

    def _simulate_logs(self, force: bool = False) -> None:
        """Simulate enrichment logs when real logs are unavailable."""
        if random.random() < 0.25 or force:
            files = ["auth.py", "user.py", "db.py", "graph.py", "utils.py"]
            filename = random.choice(files)
            self.add_log(f"Enriching {filename}...")

        if random.random() < 0.12 or force:
            self.add_log("Graph sync complete.", "OK")

    def update_context(self) -> None:
        """Refresh context/help plus analytics summary."""
        try:
            analytics_text = self.get_analytics_summary(self.app.repo_root)
            help_lines = [
                "Monitor shows RAG index stats (top right) and enrichment logs.",
                "Navigation mirrors CLI menu; press [r] to refresh, [esc] to go back.",
                "",
                "Analytics (last 7d):",
                analytics_text,
            ]
            self.query_one("#context-body", Static).update("\n".join(help_lines))
        except Exception as exc:
            self.query_one("#context-body", Static).update(
                f"[red]Context update error: {exc}[/red]"
            )

    def add_log(self, msg: str, level: str = "INF") -> None:
        """Add a log entry."""
        ts = datetime.now().strftime("%H:%M:%S")
        color_map = {"OK": "green", "INF": "cyan", "ERR": "red"}
        color = color_map.get(level, "white")
        self.logs.append(f"[dim]{ts}[/dim] [{color}]{level}[/{color}] {msg}")

    def get_repo_stats(self, repo_root: Path) -> dict[str, Any]:
        """Fetch real repo stats."""
        stats: dict[str, Any] = {
            "files_tracked": 0,
            "graph_nodes": 0,
            "token_usage": 0,
            "daemon_status": "OFFLINE",
        }

        try:
            from tools.rag_nav.tool_handlers import _load_graph

            index_db = repo_root / ".rag" / "index_v2.db"
            if index_db.exists():
                stats["daemon_status"] = "ONLINE"

                nodes, _ = _load_graph(repo_root)
                stats["graph_nodes"] = len(nodes)
                stats["files_tracked"] = len({n.get("path", "") for n in nodes if n.get("path")})

                total_content = sum(
                    len(str(n.get("metadata", {}).get("summary", ""))) for n in nodes
                )
                stats["token_usage"] = total_content // 4

        except Exception as exc:
            self.add_log(f"Stats error: {exc}", "ERR")

        return stats

    def get_analytics_summary(self, repo_root: Path) -> str:
        """Build analytics summary text."""
        analytics_db = repo_root / ".rag" / "analytics.db"
        if not analytics_db.exists():
            return "No analytics yet. Run searches to build history."

        tracker = QueryTracker(analytics_db)
        summary = tracker.get_analytics(days=7)

        lines = [
            f"Total Queries: [bold]{summary.total_queries}[/bold]",
            f"Unique Queries: [bold]{summary.unique_queries}[/bold]",
            f"Avg Results/Query: [bold]{summary.avg_results_per_query}[/bold]",
            "",
        ]

        if summary.top_queries:
            lines.append("Top Queries:")
            for query, count in summary.top_queries[:3]:
                trimmed = query if len(query) <= 42 else query[:39] + "..."
                lines.append(f"  • {trimmed} ([bold]{count}[/bold])")
            lines.append("")

        if summary.top_files:
            lines.append("Top Files:")
            for file_path, count in summary.top_files[:3]:
                display = file_path if len(file_path) <= 42 else "..." + file_path[-39:]
                lines.append(f"  • {display} ([bold]{count}[/bold])")

        return "\n".join(lines) if lines else "No analytics available."

    def action_refresh(self) -> None:
        """Manually refresh stats and analytics."""
        self.update_stats()
        self.update_context()
        self.add_log("Stats refreshed", "OK")

    def action_nav_monitor(self) -> None:
        """Stay on monitor; useful for keybinding consistency."""
        self.add_log("Already on Monitor", "INF")

    def action_nav_search(self) -> None:
        """Go to search screen."""
        try:
            from llmc.tui.screens.search import SearchScreen

            self.app.push_screen(SearchScreen())
        except Exception as exc:
            self.add_log(f"Open search failed: {exc}", "ERR")

    def action_nav_inspect(self) -> None:
        """Go to inspector screen."""
        try:
            from llmc.tui.screens.inspector import InspectorScreen

            self.app.push_screen(InspectorScreen())
        except Exception as exc:
            self.add_log(f"Open inspector failed: {exc}", "ERR")

    def action_nav_config(self) -> None:
        """Switch to configuration screen."""
        try:
            self.app.push_screen(ConfigScreen())
        except Exception as exc:
            self.add_log(f"Open config failed: {exc}", "ERR")

    def action_nav_analytics(self) -> None:
        """Switch to analytics dashboard."""
        try:
            from llmc.tui.screens.analytics import AnalyticsScreen

            self.app.push_screen(AnalyticsScreen())
        except Exception as exc:
            self.add_log(f"Open analytics failed: {exc}", "ERR")

    def action_nav_live_monitor(self) -> None:
        """Switch to live TE monitor."""
        try:
            from llmc.tui.screens.live_monitor import LiveMonitorScreen

            self.app.push_screen(LiveMonitorScreen())
        except Exception as exc:
            self.add_log(f"Open live monitor failed: {exc}", "ERR")

    def action_nav_rag_doctor(self) -> None:
        """Switch to RAG Doctor screen."""
        try:
            from llmc.tui.screens.rag_doctor import RAGDoctorScreen

            self.app.push_screen(RAGDoctorScreen())
        except Exception as exc:
            self.add_log(f"Open RAG Doctor failed: {exc}", "ERR")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle menu clicks."""
        btn_id = event.button.id or ""
        mapping = {
            "menu-1": self.action_nav_monitor,
            "menu-2": self.action_nav_search,
            "menu-3": self.action_nav_inspect,
            "menu-4": self.action_nav_config,
            "menu-5": self.action_nav_analytics,
            "menu-6": self.action_nav_live_monitor,
            "menu-7": self.action_nav_rag_doctor,
        }
        handler = mapping.get(btn_id)
        if handler:
            handler()
