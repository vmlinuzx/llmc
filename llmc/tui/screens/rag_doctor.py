from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Label,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from llmc.rag.doctor import run_rag_doctor


class RAGDoctorScreen(Screen):
    """
    RAG Doctor health dashboard for the LLMC TUI.
    Visualizes the output of tools.rag.doctor.
    """

    CSS = """
    RAGDoctorScreen {
        align: center middle;
    }

    #doctor-grid {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 2fr;
        grid-rows: 1fr;
        width: 100%;
        height: 100%;
        padding: 1;
        grid-gutter: 1;
    }

    #left-panel {
        height: 100%;
        background: $surface;
        border: solid $primary-background;
        padding: 1;
    }

    #right-panel {
        height: 100%;
        background: $surface;
        border: solid $primary-background;
        padding: 0;
    }

    #status-badge {
        width: 100%;
        height: 3;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
        background: $accent;
        color: $text;
    }

    .status-ok {
        background: $success;
        color: $text;
    }

    .status-warn {
        background: $warning;
        color: $text;
    }

    .status-broken {
        background: $error;
        color: $text;
    }

    #stats-table {
        height: auto;
        margin-bottom: 1;
    }

    #controls {
        height: auto;
        dock: bottom;
    }
    
    .code-block {
        background: $background;
        padding: 1;
        margin: 1 0;
        border: wide $primary;
    }

    .hidden {
        display: none;
    }

    .description {
        margin-bottom: 1;
        margin-left: 2;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, profile: str = "default") -> None:
        super().__init__()
        self.profile = profile
        self.report: dict[str, Any] | None = None
        # Access the repo root from the app if available, strictly read-only intent
        self.repo_root: Path = getattr(self.app, "repo_root", Path.cwd())

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="doctor-grid"):
            with Vertical(id="left-panel"):
                yield Static("Loading...", id="status-badge")
                yield Label(f"Repo: {self.repo_root}", id="repo-label")
                yield DataTable(id="stats-table")
                with Vertical(id="controls"):
                    yield Button("Refresh Report", id="btn-refresh", variant="primary")

            with Vertical(id="right-panel"):
                with TabbedContent():
                    with TabPane("Summary", id="tab-summary"):
                        yield Static("Select 'Refresh' to load data.", id="summary-text")
                    with TabPane("Top Offenders", id="tab-offenders"):
                        yield DataTable(id="offenders-table")
                    with TabPane("Guidance", id="tab-guidance"):
                        yield Static("Guidance will appear here.", id="guidance-text")
                        with Vertical(id="action-buttons", classes="hidden"):
                            yield Label("\nActions:", classes="section-header")
                            yield Button(
                                "Dry Run: Embed Pending", id="btn-embed-dry", variant="default"
                            )
                            yield Label(
                                "  - Shows a plan of up to 20 spans that would be embedded, without making changes.",
                                classes="description",
                            )
                            yield Button(
                                "Execute: Embed Pending", id="btn-embed-exec", variant="error"
                            )
                            yield Label(
                                "  - Processes up to 100 pending spans, creating their embeddings.",
                                classes="description",
                            )
                        yield Label("\nCommand Output:", id="output-label", classes="hidden")
                        yield RichLog(id="command-log", classes="hidden", markup=True)
        yield Footer()

    def on_mount(self) -> None:
        # Initialize tables
        table = self.query_one("#stats-table", DataTable)
        table.add_columns("Metric", "Value")

        offenders = self.query_one("#offenders-table", DataTable)
        offenders.add_columns("File", "Pending Spans")

        self.action_refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-refresh":
            self.action_refresh()
        elif event.button.id == "btn-embed-dry":
            self.run_worker(
                lambda: self._run_te_cmd("python3 -m llmc.rag.cli embed --limit 20"), thread=True
            )
        elif event.button.id == "btn-embed-exec":
            self.run_worker(
                lambda: self._run_te_cmd("python3 -m llmc.rag.cli embed --execute --limit 100"),
                thread=True,
            )

    def action_refresh(self) -> None:
        """Trigger a background refresh of the doctor report."""
        badge = self.query_one("#status-badge", Static)
        badge.update("Running Doctor...")
        badge.remove_class("status-ok", "status-warn", "status-broken")

        self.run_worker(self._load_data, thread=True)

    def _load_data(self) -> None:
        """Run the doctor tool in a thread (DB I/O)."""
        try:
            # Run the doctor tool directly
            report = run_rag_doctor(self.repo_root)
            self.app.call_from_thread(self.update_ui, report)
        except Exception as e:
            self.app.call_from_thread(self.show_error, str(e))

    def show_error(self, error_msg: str) -> None:
        badge = self.query_one("#status-badge", Static)
        badge.update("ERROR")
        badge.add_class("status-broken")

        summary = self.query_one("#summary-text", Static)
        summary.update(f"Failed to run RAG Doctor:\n\n{error_msg}")

    def _run_te_cmd(self, cmd_suffix: str) -> None:
        """Execute a TE command and stream output to the log."""
        log = self.query_one("#command-log", RichLog)
        self.app.call_from_thread(log.remove_class, "hidden")
        self.app.call_from_thread(self.query_one("#output-label").remove_class, "hidden")
        self.app.call_from_thread(log.clear)
        self.app.call_from_thread(log.write, f"[bold cyan]Running: ./scripts/te {cmd_suffix}[/]\n")

        try:
            # Construct command: use TE wrapper
            te_script = self.repo_root / "scripts" / "te"
            cmd = [str(te_script)] + cmd_suffix.split()

            # Set environment for TE
            env = dict(os.environ)
            env["TE_AGENT_ID"] = "manual-dave"

            proc = subprocess.Popen(
                cmd,
                cwd=self.repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                bufsize=1,
            )

            if proc.stdout:
                for line in proc.stdout:
                    self.app.call_from_thread(log.write, line.rstrip())

            proc.wait()
            if proc.returncode == 0:
                self.app.call_from_thread(log.write, "\n[bold green]Success.[/]")
                # Auto-refresh doctor stats on success if it was an execution
                if "--execute" in cmd_suffix:
                    self.app.call_from_thread(self.action_refresh)
            else:
                self.app.call_from_thread(
                    log.write, f"\n[bold red]Failed (exit code {proc.returncode}).[/]"
                )

        except Exception as e:
            self.app.call_from_thread(log.write, f"\n[bold red]Error launching command: {e}[/]")

    def update_ui(self, report: dict[str, Any]) -> None:
        self.report = report
        status = report.get("status", "UNKNOWN")
        stats = report.get("stats") or {}
        issues = report.get("issues", [])

        # 1. Update Badge
        badge = self.query_one("#status-badge", Static)
        badge.update(f"Status: {status}")
        badge.remove_class("status-ok", "status-warn", "status-broken")

        if status == "OK":
            badge.add_class("status-ok")
        elif status in ("WARN", "DEGRADED"):
            badge.add_class("status-warn")
        else:
            badge.add_class("status-broken")

        # 2. Update Stats Table
        table = self.query_one("#stats-table", DataTable)
        table.clear()
        if stats:
            table.add_rows(
                [
                    ("Files", str(stats.get("files", 0))),
                    ("Spans", str(stats.get("spans", 0))),
                    ("Enrichments", str(stats.get("enrichments", 0))),
                    ("Embeddings", str(stats.get("embeddings", 0))),
                    ("Pending Embeddings", str(stats.get("pending_embeddings", 0))),
                    ("Pending Enrichments", str(stats.get("pending_enrichments", 0))),
                    ("Orphans", str(stats.get("orphan_enrichments", 0))),
                ]
            )

        # 3. Update Summary Tab
        summary_widget = self.query_one("#summary-text", Static)
        if issues:
            summary_text = "\n".join(f"- {issue}" for issue in issues)
        else:
            summary_text = "No issues detected. RAG index is healthy."
        summary_widget.update(summary_text)

        # 4. Update Offenders Tab
        offenders_table = self.query_one("#offenders-table", DataTable)
        offenders_table.clear()
        top_files = report.get("top_pending_files", [])
        if top_files:
            for f in top_files:
                offenders_table.add_row(f.get("path", "?"), str(f.get("pending_spans", 0)))
        else:
            # If no top files but we have pending, it might be distributed or not captured
            pass

        # 5. Update Guidance Tab
        guidance_widget = self.query_one("#guidance-text", Static)
        guidance_widget.update(self._generate_guidance(report))

        # Toggle Action Buttons
        stats = report.get("stats") or {}
        actions_panel = self.query_one("#action-buttons", Vertical)
        if stats.get("pending_embeddings", 0) > 0:
            actions_panel.remove_class("hidden")
        else:
            actions_panel.add_class("hidden")

    def _generate_guidance(self, report: dict[str, Any]) -> str:
        status = report.get("status", "UNKNOWN")
        stats = report.get("stats") or {}
        pending_emb = stats.get("pending_embeddings", 0)
        orphans = stats.get("orphan_enrichments", 0)

        lines = []

        if status == "NO_DB":
            lines.append("RAG index not found. Initialize it:")
            lines.append(self._te_cmd("rag index"))
            return "\n".join(lines)

        if status == "OK":
            return "System is healthy. No actions recommended."

        if pending_emb > 0:
            lines.append(f"Found {pending_emb} spans missing embeddings.")
            lines.append("Recommended action:")
            lines.append(self._te_cmd("python3 -m llmc.rag.cli embed-missing"))
            lines.append("")

        if orphans > 0:
            lines.append(f"Found {orphans} orphan enrichments.")
            lines.append("Recommended action (investigate):")
            lines.append(self._te_cmd("python3 -m llmc.rag.cli doctor --json"))
            lines.append("")

        if not lines:
            lines.append("Check summary tab for details.")

        return "\n".join(lines)

    def _te_cmd(self, cmd_suffix: str) -> str:
        """Helper to format a copy-pasteable TE command."""
        # Assuming manual-dave for the user copy-paste
        return (
            f"```bash\n"
            f"cd {self.repo_root} && export TE_AGENT_ID=manual-dave && "
            f"./scripts/te {cmd_suffix}\n"
            f"```"
        )
