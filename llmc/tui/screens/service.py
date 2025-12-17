"""
LLMC TUI Service Screen - Daemon and repository management.

Maps to: llmc service start/stop/restart/status/logs
         llmc service repo add/remove/list
"""

import json
import os
from pathlib import Path
import subprocess
import threading

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, ScrollableContainer
from textual.widgets import Button, DataTable, Static

from llmc.tui.base import LLMCScreen


class ServiceScreen(LLMCScreen):
    """Service management - start/stop daemon, manage repos, view logs."""

    SCREEN_TITLE = "Service"

    BINDINGS = LLMCScreen.BINDINGS + [
        Binding("r", "refresh", "Refresh"),
        Binding("s", "service_start", "Start"),
        Binding("x", "service_stop", "Stop"),
        Binding("t", "service_restart", "Restart"),
        Binding("l", "toggle_logs", "Toggle Logs"),
        Binding("a", "repo_add", "Add Repo"),
    ]

    CSS = """
    ServiceScreen {
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

    #status-panel {
        height: 14;
    }

    #repos-panel {
        height: 14;
    }

    #logs-panel {
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

    #service-buttons {
        layout: horizontal;
        height: auto;
        margin-top: 1;
    }

    .svc-btn {
        min-width: 10;
        margin-right: 1;
    }

    #log-scroll {
        height: 100%;
    }

    #log-content {
        height: auto;
    }

    DataTable {
        height: 100%;
    }
    """

    def __init__(self):
        super().__init__()
        self.logs: list[str] = []
        self._log_proc: subprocess.Popen | None = None
        self._log_thread: threading.Thread | None = None
        self._show_logs = True

    def compose_content(self) -> ComposeResult:
        """Build service management layout."""
        with Grid(id="main-grid"):
            # Status panel
            status_panel = Container(id="status-panel", classes="panel")
            status_panel.border_title = "Daemon Status"
            with status_panel:
                yield Static(id="status-content")
                with Container(id="service-buttons"):
                    yield Button("[s] Start", id="btn-start", classes="svc-btn")
                    yield Button(
                        "[x] Stop", id="btn-stop", classes="svc-btn", variant="error"
                    )
                    yield Button("[t] Restart", id="btn-restart", classes="svc-btn")

            # Repos panel
            repos_panel = Container(id="repos-panel", classes="panel")
            repos_panel.border_title = "Repositories"
            with repos_panel:
                yield DataTable(id="repos-table")

            # Logs panel
            logs_panel = Container(id="logs-panel", classes="panel")
            logs_panel.border_title = "Service Logs [l to toggle]"
            with logs_panel:
                with ScrollableContainer(id="log-scroll"):
                    yield Static(id="log-content", markup=False)

    def on_mount(self) -> None:
        """Initialize service screen."""
        super().on_mount()

        # Set up repos table
        table = self.query_one("#repos-table", DataTable)
        table.add_columns("Repository", "Status", "Spans")

        self._start_log_stream()
        self.update_status()
        self.update_repos()
        self.update_logs()

        self.set_interval(3.0, self.update_status)
        self.set_interval(5.0, self.update_repos)
        self.set_interval(0.5, self.update_logs)

    def on_unmount(self) -> None:
        """Clean up on exit."""
        self._stop_log_stream()

    def update_status(self) -> None:
        """Refresh daemon status."""
        try:
            # Check systemd service status
            result = subprocess.run(
                ["systemctl", "--user", "is-active", "llmc-rag.service"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            is_active = result.stdout.strip() == "active"

            # Get more details if active
            if is_active:
                pid_result = subprocess.run(
                    [
                        "systemctl",
                        "--user",
                        "show",
                        "-p",
                        "MainPID",
                        "llmc-rag.service",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                pid = (
                    pid_result.stdout.strip().split("=")[1]
                    if "=" in pid_result.stdout
                    else "?"
                )

                status_color = "green"
                status_text = "RUNNING"
            else:
                pid = "-"
                status_color = "red"
                status_text = "STOPPED"

            content = "\n".join(
                [
                    f"[#666680]Status:[/]  [bold {status_color}]{status_text}[/]",
                    f"[#666680]PID:[/]     [bold]{pid}[/]",
                    "[#666680]Service:[/] llmc-rag.service",
                ]
            )

            self.query_one("#status-content", Static).update(content)

        except Exception as e:
            self.query_one("#status-content", Static).update(
                f"[red]Error checking status: {e}[/]"
            )

    def update_repos(self) -> None:
        """Refresh repository list."""
        try:
            table = self.query_one("#repos-table", DataTable)
            table.clear()

            repos = self._get_registered_repos()

            if not repos:
                # Could optionally show a placeholder or empty state
                pass

            for repo_path_str in repos:
                repo_path = Path(repo_path_str)
                status = "Active"
                spans = "?"

                # Try to get stats
                stats = self._get_repo_stats(repo_path)
                if stats:
                    spans = str(stats.get("spans", "?"))

                table.add_row(str(repo_path), status, spans)

        except Exception as e:
            self.notify(f"Error loading repos: {e}", severity="error")

    def _get_registered_repos(self) -> list[str]:
        """Get list of registered repositories."""
        # Try importing ServiceState
        try:
            from llmc.rag.service import ServiceState

            return ServiceState().state.get("repos", [])
        except ImportError:
            # Fallback to reading file directly
            return self._read_repos_from_file()
        except Exception:
            return []

    def _read_repos_from_file(self) -> list[str]:
        """Read repos from state file directly (fallback)."""
        state_override = os.environ.get("LLMC_RAG_SERVICE_STATE")
        if state_override:
            state_file = Path(os.path.expanduser(state_override)).resolve()
        else:
            state_file = Path.home() / ".llmc" / "rag-service.json"

        if state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                return data.get("repos", [])
            except Exception:
                pass
        return []

    def _get_repo_stats(self, repo_path: Path) -> dict | None:
        """Get basic stats for a repo."""
        try:
            from llmc.rag.doctor import run_rag_doctor

            report = run_rag_doctor(repo_path)
            return report.get("stats")
        except ImportError:
            return None
        except Exception:
            return None

    def _start_log_stream(self) -> None:
        """Start streaming service logs."""
        if self._log_proc is not None:
            return

        try:
            self._log_proc = subprocess.Popen(
                [
                    "journalctl",
                    "--user",
                    "-u",
                    "llmc-rag.service",
                    "-f",
                    "-n",
                    "50",
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
                            if len(self.logs) > 200:
                                self.logs = self.logs[-100:]
                except Exception:
                    pass

            self._log_thread = threading.Thread(target=reader, daemon=True)
            self._log_thread.start()

        except Exception as e:
            self.logs.append(f"[Log stream error: {e}]")

    def _stop_log_stream(self) -> None:
        """Stop log streaming."""
        if self._log_proc:
            try:
                self._log_proc.terminate()
            except Exception:
                pass
            self._log_proc = None

    def update_logs(self) -> None:
        """Refresh log display."""
        if not self._show_logs:
            return

        content = (
            "\n".join(self.logs[-50:]) if self.logs else "[dim]No logs yet...[/dim]"
        )
        self.query_one("#log-content", Static).update(content)

        scroll = self.query_one("#log-scroll", ScrollableContainer)
        scroll.scroll_end(animate=False)

    # Button handlers
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        btn = event.button.id
        if btn == "btn-start":
            self.action_service_start()
        elif btn == "btn-stop":
            self.action_service_stop()
        elif btn == "btn-restart":
            self.action_service_restart()

    # Service control actions
    def action_refresh(self) -> None:
        """Manually refresh status."""
        self.update_status()
        self.update_repos()
        self.notify("Refreshed", severity="information")

    def action_service_start(self) -> None:
        """Start the RAG daemon."""
        self.notify("Starting daemon...", severity="information")
        self._run_systemctl("start")

    def action_service_stop(self) -> None:
        """Stop the RAG daemon."""
        self.notify("Stopping daemon...", severity="warning")
        self._run_systemctl("stop")

    def action_service_restart(self) -> None:
        """Restart the RAG daemon."""
        self.notify("Restarting daemon...", severity="information")
        self._run_systemctl("restart")

    def action_toggle_logs(self) -> None:
        """Toggle log display."""
        self._show_logs = not self._show_logs
        state = "shown" if self._show_logs else "hidden"
        self.notify(f"Logs {state}", severity="information")

    def action_repo_add(self) -> None:
        """Add a repository (placeholder)."""
        self.notify(
            "Repo add: Use CLI 'llmc service repo add <path>'", severity="information"
        )

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

                # Refresh status after action
                self.call_from_thread(self.update_status)

            except Exception as e:
                self.logs.append(f"[ERR] Service {action}: {e}")

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
