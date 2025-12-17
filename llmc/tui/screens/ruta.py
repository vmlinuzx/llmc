"""
LLMC TUI RUTA Screen - User Testing Interface.
"""

import subprocess
import sys
import threading

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Vertical
from textual.message import Message
from textual.widgets import Button, DataTable, RichLog

from llmc.core import find_repo_root
from llmc.tui.base import LLMCScreen


class RUTAScreen(LLMCScreen):
    """Screen for running RUTA user tests."""

    SCREEN_TITLE = "RUTA (Ruthless User Testing Agent)"

    BINDINGS = LLMCScreen.BINDINGS + [
        Binding("r", "run_selected", "Run Selected"),
        Binding("c", "clear_logs", "Clear Logs"),
    ]

    CSS = """
    RUTAScreen {
        layout: vertical;
    }

    #main-grid {
        layout: grid;
        grid-size: 2 1;
        grid-columns: 1fr 2fr;
        grid-gutter: 1;
        padding: 1;
        height: 1fr;
    }

    #left-panel {
        height: 100%;
        background: #1a1a2e;
        border: heavy #00b8ff;
        border-title-color: #00ff9f;
        border-title-style: bold;
    }

    #right-panel {
        height: 100%;
        background: #1a1a2e;
        border: heavy #00b8ff;
        border-title-color: #00ff9f;
        border-title-style: bold;
    }

    #scenario-table {
        height: 1fr;
    }

    #log-output {
        height: 1fr;
        background: #0d0d1a;
        color: #e0e0e0;
    }

    #controls {
        height: auto;
        padding: 1;
        align: center middle;
    }

    .action-btn {
        margin: 0 1;
        min-width: 16;
    }
    """

    class RunFinished(Message):
        """Message sent when a RUTA run finishes."""

        def __init__(self, success: bool, output: str) -> None:
            self.success = success
            self.output = output
            super().__init__()

    def __init__(self):
        super().__init__()
        self._run_thread: threading.Thread | None = None
        self._is_running = False

    def compose_content(self) -> ComposeResult:
        """Build RUTA screen layout."""
        with Grid(id="main-grid"):
            # Left Panel: Scenarios List
            with Vertical(id="left-panel") as left:
                left.border_title = "Scenarios"
                yield DataTable(id="scenario-table", cursor_type="row")
                with Container(id="controls"):
                    yield Button(
                        "Run Selected (r)",
                        id="btn-run",
                        classes="action-btn",
                        variant="primary",
                    )

            # Right Panel: Output Logs
            with Vertical(id="right-panel") as right:
                right.border_title = "Execution Log"
                yield RichLog(id="log-output", markup=True, wrap=True)

    def on_mount(self) -> None:
        """Initialize screen."""
        super().on_mount()
        self.load_scenarios()

    def load_scenarios(self) -> None:
        """Load scenarios from tests/usertests/*.yaml."""
        table = self.query_one("#scenario-table", DataTable)
        table.clear()
        table.add_columns("Scenario", "Description")

        try:
            repo_root = find_repo_root()
            scenario_dir = repo_root / "tests/usertests"
            if not scenario_dir.exists():
                self.notify(
                    f"No scenario directory found at {scenario_dir}", severity="warning"
                )
                return

            # Find all yaml files
            scenarios = []
            for file in scenario_dir.glob("*.yaml"):
                # Basic parsing to get description if possible, else just filename
                desc = "No description"
                try:
                    import yaml

                    with open(file) as f:
                        data = yaml.safe_load(f)
                        desc = data.get("description", desc)
                except Exception:
                    pass
                scenarios.append((file.stem, desc))

            scenarios.sort()
            for name, desc in scenarios:
                table.add_row(name, desc, key=name)

        except Exception as e:
            self.notify(f"Error loading scenarios: {e}", severity="error")

    def action_run_selected(self) -> None:
        """Run the selected scenario."""
        if self._is_running:
            self.notify("A test is already running.", severity="warning")
            return

        table = self.query_one("#scenario-table", DataTable)
        try:
            row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
            if row_key:
                self.run_scenario(row_key.value)
            else:
                self.notify("No scenario selected.", severity="warning")
        except Exception:
            self.notify("Please select a scenario first.", severity="warning")

    def action_clear_logs(self) -> None:
        """Clear the log output."""
        self.query_one("#log-output", RichLog).clear()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn-run":
            self.action_run_selected()

    def run_scenario(self, scenario_name: str) -> None:
        """Execute the RUTA scenario in a background thread."""
        self._is_running = True
        log = self.query_one("#log-output", RichLog)
        log.write(f"[bold cyan]Starting RUTA scenario: {scenario_name}[/]")
        log.write("-" * 50)

        self.query_one("#btn-run", Button).disabled = True

        def run_thread():
            try:
                # Construct command: python -m llmc.main usertest run <scenario>
                # We use sys.executable to ensure we use the same python environment
                cmd = [
                    sys.executable,
                    "-m",
                    "llmc.main",
                    "usertest",
                    "run",
                    scenario_name,
                ]

                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=find_repo_root(),  # Run from repo root
                )

                for line in process.stdout:
                    # Write to log in the main thread
                    self.app.call_from_thread(log.write, line.rstrip())

                process.wait()
                success = process.returncode == 0

                if success:
                    msg = f"[bold green]Scenario {scenario_name} passed![/]"
                else:
                    msg = f"[bold red]Scenario {scenario_name} failed with exit code {process.returncode}[/]"

                self.app.call_from_thread(log.write, "-" * 50)
                self.app.call_from_thread(log.write, msg)

                # Re-enable button
                def cleanup():
                    self._is_running = False
                    self.query_one("#btn-run", Button).disabled = False
                    self.notify(f"RUTA finished: {'SUCCESS' if success else 'FAILURE'}")

                self.app.call_from_thread(cleanup)

            except Exception as e:
                self.app.call_from_thread(
                    log.write, f"[bold red]Execution error: {e}[/]"
                )

                def cleanup_error():
                    self._is_running = False
                    self.query_one("#btn-run", Button).disabled = False

                self.app.call_from_thread(cleanup_error)

        self._run_thread = threading.Thread(target=run_thread, daemon=True)
        self._run_thread.start()
