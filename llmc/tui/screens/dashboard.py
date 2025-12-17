"""
LLMC TUI Dashboard Screen - Main overview with stats and quick actions.

Maps to: llmc stats, llmc index, llmc enrich, llmc doctor, llmc benchmark
"""

from datetime import datetime
from pathlib import Path
import subprocess
import threading

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, ScrollableContainer
from textual.widgets import Button, Static

from llmc.tui.base import LLMCScreen


class DashboardScreen(LLMCScreen):
    """Main dashboard - system overview, quick actions, live logs."""

    SCREEN_TITLE = "Dashboard"

    BINDINGS = LLMCScreen.BINDINGS + [
        Binding("r", "refresh", "Refresh"),
        Binding("s", "service_start", "Start"),
        Binding("x", "service_stop", "Stop"),
    ]

    CSS = """
    DashboardScreen {
        layout: vertical;
    }

    #main-grid {
        layout: grid;
        grid-size: 2 2;
        grid-columns: 1fr 1fr;
        grid-rows: auto 1fr;
        grid-gutter: 1;
        padding: 1;
        height: 1fr;
    }

    #stats-panel {
        height: 12;
    }

    #actions-panel {
        height: 12;
    }

    #log-panel {
        row-span: 1;
        column-span: 2;
        height: 100%;
        min-height: 10;
    }

    .panel {
        background: #1a1a2e;
        border: heavy #00b8ff;
        border-title-color: #00ff9f;
        border-title-style: bold;
        padding: 0 1;
    }

    #action-buttons {
        layout: horizontal;
        height: auto;
        align: center middle;
    }

    .action-btn {
        min-width: 16;
        height: 3;
        margin: 0 2;
    }

    #log-scroll {
        height: 100%;
        scrollbar-gutter: stable;
    }

    #log-content {
        height: auto;
    }

    .stat-row {
        height: auto;
        margin: 0;
    }
    """

    def __init__(self):
        super().__init__()
        self.logs: list[str] = []
        self._log_proc: subprocess.Popen | None = None
        self._log_thread: threading.Thread | None = None
        self._max_log_lines = 500
        self._user_scrolled = False  # Track if user scrolled up
        self.start_time = datetime.now()

    def compose_content(self) -> ComposeResult:
        """Build dashboard layout."""
        with Grid(id="main-grid"):
            # Stats panel
            stats = Container(id="stats-panel", classes="panel")
            stats.border_title = "System Status"
            with stats:
                yield Static(id="stats-content")

            # Quick actions panel
            actions = Container(id="actions-panel", classes="panel")
            actions.border_title = "Service Control"
            with actions:
                with Container(id="action-buttons"):
                    yield Button("(s) Start", id="btn-start", classes="action-btn")
                    yield Button(
                        "(x) Stop", id="btn-stop", classes="action-btn", variant="error"
                    )

            # Log panel (spans both columns)
            logs = Container(id="log-panel", classes="panel")
            logs.border_title = "Enrichment Log"
            with logs:
                with ScrollableContainer(id="log-scroll"):
                    yield Static(id="log-content", markup=False)

    def on_mount(self) -> None:
        """Initialize dashboard."""
        super().on_mount()
        self._start_log_stream()
        self.update_stats()
        self.update_logs()

        # Set up refresh timers
        self.set_interval(2.0, self.update_stats)
        self.set_interval(0.5, self.update_logs)

    def on_unmount(self) -> None:
        """Clean up on exit."""
        self._stop_log_stream()

    def update_stats(self) -> None:
        """Refresh system statistics using RAG Doctor."""
        try:
            repo_root = getattr(self.app, "repo_root", Path.cwd())
            report = self._get_doctor_report(repo_root)

            # Check daemon status via systemd
            daemon_status = self._check_daemon_status()
            daemon_color = "green" if daemon_status == "ONLINE" else "red"

            stats = report.get("stats") or {}
            status = report.get("status", "UNKNOWN")

            # Calculate percentages
            total_spans = stats.get("spans", 0)
            enriched = stats.get("enrichments", 0)
            embedded = stats.get("embeddings", 0)
            pending_enrich = stats.get("pending_enrichments", 0)
            pending_embed = stats.get("pending_embeddings", 0)

            enrich_pct = (
                f"{enriched / total_spans * 100:.0f}%" if total_spans > 0 else "N/A"
            )
            embed_pct = (
                f"{embedded / total_spans * 100:.0f}%" if total_spans > 0 else "N/A"
            )

            # Status color
            status_color = (
                "green" if status == "OK" else "yellow" if status == "WARN" else "red"
            )

            uptime = str(datetime.now() - self.start_time).split(".")[0]

            content = "\n".join(
                [
                    f"[#666680]Daemon:[/]     [bold {daemon_color}]{daemon_status}[/]   [#666680]Health:[/] [bold {status_color}]{status}[/]",
                    f"[#666680]Files:[/]      [bold]{stats.get('files', 0):,}[/]",
                    f"[#666680]Spans:[/]      [bold]{total_spans:,}[/]",
                    f"[#666680]Enriched:[/]   [bold green]{enriched:,}[/] ({enrich_pct})  [#666680]Pending:[/] [yellow]{pending_enrich:,}[/]",
                    f"[#666680]Embedded:[/]   [bold cyan]{embedded:,}[/] ({embed_pct})  [#666680]Pending:[/] [yellow]{pending_embed:,}[/]",
                    f"[#666680]Uptime:[/]     [bold]{uptime}[/]",
                ]
            )

            # Add first issue if any
            issues = report.get("issues", [])
            if issues:
                content += (
                    f"\n[#666680]Issue:[/]      [yellow]{issues[0][:50]}...[/]"
                    if len(issues[0]) > 50
                    else f"\n[#666680]Issue:[/]      [yellow]{issues[0]}[/]"
                )

            self.query_one("#stats-content", Static).update(content)
        except Exception as e:
            self.query_one("#stats-content", Static).update(
                f"[red]Error loading stats: {e}[/]"
            )

    def _get_doctor_report(self, repo_root: Path) -> dict:
        """Get RAG doctor health report."""
        try:
            from llmc.rag.doctor import run_rag_doctor

            return run_rag_doctor(repo_root, verbose=False)
        except Exception as e:
            return {
                "status": "ERROR",
                "stats": {},
                "issues": [str(e)],
            }

    def _check_daemon_status(self) -> str:
        """Check if RAG daemon is running via systemd."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", "llmc-rag.service"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            return "ONLINE" if result.stdout.strip() == "active" else "OFFLINE"
        except Exception:
            return "UNKNOWN"

    def _start_log_stream(self) -> None:
        """Start streaming logs from the RAG daemon."""
        if self._log_proc is not None:
            return

        try:
            # Try to stream from journalctl
            self._log_proc = subprocess.Popen(
                [
                    "journalctl",
                    "--user",
                    "-u",
                    "llmc-rag.service",
                    "-f",
                    "-n",
                    str(self._max_log_lines),
                    "--no-pager",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            def reader():
                try:
                    for line in self._log_proc.stdout:
                        line = line.rstrip()
                        if line:
                            self.logs.append(line)
                            if len(self.logs) > self._max_log_lines * 2:
                                self.logs = self.logs[-self._max_log_lines :]
                except Exception:
                    pass

            self._log_thread = threading.Thread(target=reader, daemon=True)
            self._log_thread.start()

        except Exception as e:
            self.logs.append(f"[Log stream error: {e}]")

    def _stop_log_stream(self) -> None:
        """Stop log streaming process."""
        if self._log_proc:
            try:
                self._log_proc.terminate()
            except Exception:
                pass
            self._log_proc = None

    def update_logs(self) -> None:
        """Refresh log display - only auto-scroll if at bottom."""
        if not self.logs:
            content = "[dim]Waiting for logs...[/dim]"
        else:
            content = "\n".join(self.logs[-self._max_log_lines :])

        log_widget = self.query_one("#log-content", Static)
        log_widget.update(content)

        # Only auto-scroll if user hasn't scrolled up
        scroll = self.query_one("#log-scroll", ScrollableContainer)
        if not self._user_scrolled:
            scroll.scroll_end(animate=False)

    def on_scroll(self, event) -> None:
        """Track when user scrolls to disable auto-scroll."""
        scroll = self.query_one("#log-scroll", ScrollableContainer)
        # If user scrolled up (not at bottom), disable auto-scroll
        # Re-enable when they scroll back to bottom
        at_bottom = scroll.scroll_y >= scroll.max_scroll_y - 1
        self._user_scrolled = not at_bottom

    # Button handlers
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        button_id = event.button.id
        if button_id == "btn-start":
            self.action_service_start()
        elif button_id == "btn-stop":
            self.action_service_stop()

    # Quick action handlers
    def action_refresh(self) -> None:
        """Manually refresh stats."""
        self.update_stats()
        self.notify("Refreshed", severity="information")

    def action_service_start(self) -> None:
        """Start the RAG daemon."""
        self.notify("Starting service...", severity="information")
        self._run_systemctl("start")

    def action_service_stop(self) -> None:
        """Stop the RAG daemon."""
        self.notify("Stopping service...", severity="warning")
        self._run_systemctl("stop")

    def _run_systemctl(self, action: str) -> None:
        """Run a systemctl command asynchronously."""

        def run():
            try:
                result = subprocess.run(
                    ["systemctl", "--user", action, "llmc-rag.service"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    self.logs.append(f"[OK] Service {action} successful")
                else:
                    self.logs.append(f"[ERR] Service {action}: {result.stderr[:100]}")
                # Refresh stats after action
                self.call_from_thread(self.update_stats)
            except Exception as e:
                self.logs.append(f"[ERR] Service {action}: {e}")

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
