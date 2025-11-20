#!/usr/bin/env python3
"""Monitor Screen - real-time system dashboard with analytics."""
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from textual.app import ComposeResult
from textual.widgets import Static, Button
from textual.containers import Container, Grid, Vertical, ScrollableContainer
from textual.screen import Screen

from tools.rag.analytics import QueryTracker
from llmc.tui.screens.config import ConfigScreen


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
        ("5", "nav_doctor", "System Doctor"),
        ("6", "nav_agents", "Agent Status"),
    ]

    def __init__(self):
        super().__init__()
        self.logs = []
        self.start_time = datetime.now()
        self.menu_items = [
            ("1", "Monitor System", self.action_nav_monitor),
            ("2", "Search Code", self.action_nav_search),
            ("3", "Code Inspector", self.action_nav_inspect),
            ("4", "Configuration", self.action_nav_config),
            ("5", "System Doctor", self.action_nav_doctor),
            ("6", "Agent Status", self.action_nav_agents),
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
                    yield Static(id="log-output")

        yield Static("[q] Quit   [r] Refresh   [esc] Back", id="footer")

    def on_mount(self) -> None:
        """Start timers when mounted."""
        self.query_one("#header", Static).update(
            f"LLMC Monitor :: repo {self.app.repo_root}"
        )
        self.update_menu()
        self.update_stats()
        self.update_logs(force=True)
        self.update_context()

        self.set_interval(2.0, self.update_stats)
        self.set_interval(0.7, self.update_logs)
        self.set_interval(5.0, self.update_context)

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
        """Simulate or refresh log output."""
        if random.random() < 0.25 or force:
            files = ["auth.py", "user.py", "db.py", "graph.py", "utils.py"]
            filename = random.choice(files)
            self.add_log(f"Enriching {filename}...")

        if random.random() < 0.12 or force:
            self.add_log("Graph sync complete.", "OK")

        log_text = "\n".join(self.logs[-20:])
        self.query_one("#log-output", Static).update(log_text or "Awaiting logs...")

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

    def get_repo_stats(self, repo_root: Path) -> Dict[str, Any]:
        """Fetch real repo stats."""
        stats: Dict[str, Any] = {
            "files_tracked": 0,
            "graph_nodes": 0,
            "token_usage": 0,
            "daemon_status": "OFFLINE",
        }

        try:
            from tools.rag_nav.metadata import load_status
            from tools.rag_nav.tool_handlers import _load_graph

            index_db = repo_root / ".rag" / "index_v2.db"
            if index_db.exists():
                stats["daemon_status"] = "ONLINE"

                nodes, _ = _load_graph(repo_root)
                stats["graph_nodes"] = len(nodes)
                stats["files_tracked"] = len(
                    {n.get("path", "") for n in nodes if n.get("path")}
                )

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

    def action_nav_doctor(self) -> None:
        self.add_log("System Doctor not implemented yet", "INF")

    def action_nav_agents(self) -> None:
        self.add_log("Agent Status not implemented yet", "INF")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle menu clicks."""
        btn_id = event.button.id or ""
        mapping = {
            "menu-1": self.action_nav_monitor,
            "menu-2": self.action_nav_search,
            "menu-3": self.action_nav_inspect,
            "menu-4": self.action_nav_config,
            "menu-5": self.action_nav_doctor,
            "menu-6": self.action_nav_agents,
        }
        handler = mapping.get(btn_id)
        if handler:
            handler()
