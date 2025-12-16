"""
LLMC TUI Docs Screen - Documentation generation status and controls.

Maps to: llmc docs status, llmc docs generate
"""

from datetime import datetime
from pathlib import Path
import threading
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, ScrollableContainer
from textual.widgets import Button, Static, Label
from textual.worker import Worker, WorkerState

from llmc.tui.base import LLMCScreen
from llmc.docgen.config import get_output_dir, get_require_rag_fresh, load_docgen_backend
from llmc.docgen.orchestrator import DocgenOrchestrator
from tools.rag.database import Database
from llmc.core import find_repo_root, load_config


class DocsScreen(LLMCScreen):
    """Documentation generation screen - status and controls."""

    SCREEN_TITLE = "Documentation Generation"

    BINDINGS = LLMCScreen.BINDINGS + [
        Binding("r", "refresh", "Refresh Status"),
        Binding("g", "generate_all", "Generate All"),
        Binding("f", "force_generate", "Force Generate"),
    ]

    CSS = """
    DocsScreen {
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
        height: 12;
    }

    #controls-panel {
        height: 12;
    }

    #output-panel {
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

    #control-buttons {
        layout: horizontal;
        height: auto;
        align: center middle;
    }

    .control-btn {
        min-width: 20;
        height: 3;
        margin: 0 2;
    }

    #output-scroll {
        height: 100%;
        scrollbar-gutter: stable;
    }

    #output-content {
        height: auto;
    }

    .status-row {
        height: auto;
        margin: 0;
    }
    """

    def __init__(self):
        super().__init__()
        self.logs: list[str] = []
        self._max_log_lines = 500
        self._user_scrolled = False
        self.repo_root = find_repo_root()
        self.config = load_config(self.repo_root)

    def compose_content(self) -> ComposeResult:
        """Build docs screen layout."""
        with Grid(id="main-grid"):
            # Status panel
            status = Container(id="status-panel", classes="panel")
            status.border_title = "Docgen Status"
            with status:
                yield Static(id="status-content")

            # Controls panel
            controls = Container(id="controls-panel", classes="panel")
            controls.border_title = "Controls"
            with controls:
                with Container(id="control-buttons"):
                    yield Button("(g) Generate All", id="btn-generate", classes="control-btn", variant="primary")
                    yield Button("(f) Force All", id="btn-force", classes="control-btn", variant="warning")

            # Output panel
            output = Container(id="output-panel", classes="panel")
            output.border_title = "Generation Output"
            with output:
                with ScrollableContainer(id="output-scroll"):
                    yield Static(id="output-content", markup=False)

    def on_mount(self) -> None:
        """Initialize docs screen."""
        super().on_mount()
        self.update_status()
        self.log_message("Ready.")

    def update_status(self) -> None:
        """Refresh docgen status."""
        try:
            # Check if docgen is enabled
            backend = load_docgen_backend(self.repo_root, self.config)
            enabled = backend is not None
            enabled_str = "[green]Enabled[/]" if enabled else "[red]Disabled[/]"

            output_dir = get_output_dir(self.config)
            require_rag = get_require_rag_fresh(self.config)

            # Load database
            candidates = [
                self.repo_root / ".rag" / "index_v2.db",
                self.repo_root / ".llmc" / "index_v2.db",
                self.repo_root / ".llmc" / "rag" / "index.db",
            ]

            db_path = None
            for p in candidates:
                if p.exists():
                    db_path = p
                    break

            if not db_path:
                db_status = "[red]Not Found[/]"
                total_files = 0
            else:
                db = Database(db_path)
                stats = db.stats()
                total_files = stats["files"]
                db_status = f"[green]Connected[/] ({db_path.name})"

            # Count docs
            docs_dir = self.repo_root / output_dir
            doc_count = 0
            if docs_dir.exists():
                doc_count = len(list(docs_dir.rglob("*.md")))

            coverage = 0
            if total_files > 0:
                coverage = (doc_count / total_files) * 100

            content = "\n".join([
                f"[#666680]Status:[/]           {enabled_str}",
                f"[#666680]Output Dir:[/]       [bold]{output_dir}[/]",
                f"[#666680]Require Fresh:[/]    [bold]{require_rag}[/]",
                f"[#666680]RAG DB:[/]           {db_status}",
                "",
                f"[#666680]Source Files:[/]     [bold]{total_files:,}[/]",
                f"[#666680]Generated Docs:[/]   [bold]{doc_count:,}[/]",
                f"[#666680]Coverage:[/]         [bold cyan]{coverage:.1f}%[/]",
            ])

            self.query_one("#status-content", Static).update(content)

        except Exception as e:
            self.query_one("#status-content", Static).update(
                f"[red]Error loading status: {e}[/]"
            )

    def log_message(self, message: str) -> None:
        """Add message to output log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {message}")
        if len(self.logs) > self._max_log_lines:
            self.logs = self.logs[-self._max_log_lines:]

        content = "\n".join(self.logs)
        self.query_one("#output-content", Static).update(content)

        # Auto-scroll if needed
        scroll = self.query_one("#output-scroll", ScrollableContainer)
        if not self._user_scrolled:
            scroll.scroll_end(animate=False)

    def on_scroll(self, event) -> None:
        """Track scrolling."""
        scroll = self.query_one("#output-scroll", ScrollableContainer)
        at_bottom = scroll.scroll_y >= scroll.max_scroll_y - 1
        self._user_scrolled = not at_bottom

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        button_id = event.button.id
        if button_id == "btn-generate":
            self.action_generate_all()
        elif button_id == "btn-force":
            self.action_force_generate()

    def action_refresh(self) -> None:
        """Refresh status."""
        self.update_status()
        self.notify("Status refreshed", severity="information")

    def action_generate_all(self) -> None:
        """Trigger doc generation for all files."""
        self.run_generation(force=False)

    def action_force_generate(self) -> None:
        """Trigger forced doc generation for all files."""
        self.run_generation(force=True)

    def run_generation(self, force: bool) -> None:
        """Run docgen in a worker thread."""
        self.query_one("#btn-generate", Button).disabled = True
        self.query_one("#btn-force", Button).disabled = True

        force_str = " (FORCE)" if force else ""
        self.log_message(f"Starting generation{force_str}...")
        self.notify(f"Docgen started{force_str}...")

        self.run_worker(
            self._generate_worker(force),
            exclusive=True,
            thread=True,
            group="docgen"
        )

    def _generate_worker(self, force: bool):
        """Worker function for generation."""
        try:
            # Re-check backend/db in worker to be safe
            backend = load_docgen_backend(self.repo_root, self.config)
            if not backend:
                self.call_from_thread(self.log_message, "Error: Docgen disabled in config")
                return

            candidates = [
                self.repo_root / ".rag" / "index_v2.db",
                self.repo_root / ".llmc" / "index_v2.db",
                self.repo_root / ".llmc" / "rag" / "index.db",
            ]
            db_path = None
            for p in candidates:
                if p.exists():
                    db_path = p
                    break

            if not db_path:
                self.call_from_thread(self.log_message, "Error: RAG database not found")
                return

            db = Database(db_path)

            output_dir = get_output_dir(self.config)
            require_rag_fresh = get_require_rag_fresh(self.config)

            orchestrator = DocgenOrchestrator(
                repo_root=self.repo_root,
                backend=backend,
                db=db,
                output_dir=output_dir,
                require_rag_fresh=require_rag_fresh,
            )

            # Discover files
            self.call_from_thread(self.log_message, "Discovering files...")
            rows = db.conn.execute("SELECT path FROM files").fetchall()
            file_paths = [Path(row[0]) for row in rows]
            self.call_from_thread(self.log_message, f"Found {len(file_paths)} files.")

            # Process batch
            # We can't easily stream progress from orchestrator yet without modifying it,
            # so we'll just wait for the batch.
            # Ideally, we'd process one by one here to update UI.

            from llmc.docgen.graph_context import load_graph_indices
            self.call_from_thread(self.log_message, "Loading graph context...")
            cached_graph = load_graph_indices(self.repo_root)

            processed = 0
            generated = 0
            noop = 0
            skipped = 0
            errors = 0
            total = len(file_paths)

            for rel_path in file_paths:
                try:
                    result = orchestrator.process_file(rel_path, force=force, cached_graph=cached_graph)
                    processed += 1

                    if result.status == "generated":
                        generated += 1
                        self.call_from_thread(self.log_message, f"Generated: {rel_path}")
                    elif result.status == "noop":
                        noop += 1
                    elif result.status == "skipped":
                        skipped += 1
                    elif result.status == "error":
                        errors += 1
                        self.call_from_thread(self.log_message, f"Error {rel_path}: {result.reason}")

                    # Update status periodically
                    if processed % 10 == 0:
                        self.call_from_thread(self.update_status)

                except Exception as e:
                    errors += 1
                    self.call_from_thread(self.log_message, f"Exception processing {rel_path}: {e}")

            self.call_from_thread(self.log_message, "-" * 40)
            self.call_from_thread(self.log_message, "Batch Complete:")
            self.call_from_thread(self.log_message, f"Total: {total}")
            self.call_from_thread(self.log_message, f"Generated: {generated}")
            self.call_from_thread(self.log_message, f"No-op: {noop}")
            self.call_from_thread(self.log_message, f"Skipped: {skipped}")
            self.call_from_thread(self.log_message, f"Errors: {errors}")

            self.call_from_thread(self.update_status)

        except Exception as e:
            self.call_from_thread(self.log_message, f"Fatal error: {e}")
        finally:
            self.call_from_thread(self._enable_buttons)

    def _enable_buttons(self) -> None:
        """Re-enable control buttons."""
        self.query_one("#btn-generate", Button).disabled = False
        self.query_one("#btn-force", Button).disabled = False
