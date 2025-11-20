#!/usr/bin/env python3
"""
Inspector Screen - LLM-Optimized Source Viewer
"""
from pathlib import Path
from typing import Any, Dict, Optional

from textual import events
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Static, Input, Button, Checkbox, Label
from textual.message import Message

from tools.rag.inspector import inspect_entity, InspectionResult

class InspectorScreen(Screen):
    """
    Screen for fast inspection of files/symbols with graph + enrichment context.
    Uses the LLM-optimized 'rag inspect' logic.
    """
    
    CSS = """
    InspectorScreen {
        layout: grid;
        grid-size: 2 1;
        grid-columns: 30% 70%;
        padding: 1;
        background: $surface;
    }

    #sidebar {
        height: 100%;
        border-right: heavy $primary;
        padding-right: 1;
    }
    
    #main-content {
        height: 100%;
        padding-left: 1;
    }

    .panel-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
        padding-bottom: 1;
        border-bottom: solid $secondary;
    }
    
    #input-container {
        height: auto;
        margin-bottom: 2;
        padding: 1;
        border: solid $secondary;
    }
    
    #path-input {
        margin-bottom: 1;
    }
    
    #inspect-btn {
        width: 100%;
        margin-top: 1;
    }

    .section-header {
        text-style: bold;
        color: $primary;
        margin-top: 1;
        background: $surface-darken-1;
        padding: 0 1;
    }

    .data-row {
        padding-left: 1;
    }
    
    .snippet-box {
        border: solid $secondary;
        padding: 0 1;
        margin-top: 1;
        background: $surface-darken-1;
    }
    
    .error-msg {
        color: $error;
        text-style: bold;
    }
    
    #status-bar {
        dock: bottom;
        height: 1;
        background: $primary;
        color: $text;
    }
    """
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("1", "nav_monitor", "Monitor"),
        ("2", "nav_search", "Search"),
        ("3", "nav_inspect", "Inspect"),
    ]

    def compose(self) -> ComposeResult:
        # Left Sidebar
        with Vertical(id="sidebar"):
            yield Static("Inspect Entity", classes="panel-title")
            with Container(id="input-container"):
                yield Label("Path or Symbol:")
                yield Input(placeholder="e.g. src/main.py", id="path-input")
                yield Checkbox("Full Source", id="full-source-check")
                yield Button("Inspect", id="inspect-btn", variant="primary")
            
            yield Static("Tips:\n• Enter a file path or a symbol name.\n• Graph & Enrichment data will appear on the right.\n• Fast & Token-optimized.", classes="data-row")

        # Right Main Content
        with Vertical(id="main-content"):
            yield Static("Results", classes="panel-title")
            with ScrollableContainer(id="results-container"):
                yield Static("Enter a target to inspect.", id="placeholder-text")

        yield Static(" [esc] Back  [1] Monitor  [2] Search  [3] Inspect ", id="status-bar")

    def on_mount(self) -> None:
        self.query_one("#path-input").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "inspect-btn":
            self.action_inspect()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "path-input":
            self.action_inspect()

    def action_inspect(self) -> None:
        """Perform inspection using tools.rag.inspector."""
        target = self.query_one("#path-input", Input).value.strip()
        full_source = self.query_one("#full-source-check", Checkbox).value
        
        if not target:
            self._show_error("Please enter a path or symbol.")
            return
            
        container = self.query_one("#results-container")
        container.remove_children()
        container.mount(Static(f"Inspecting '{target}'...", classes="data-row"))
        
        try:
            # Direct call to the logic we just built
            repo_root = self.app.repo_root
            # Heuristic: if it looks like a path, pass path. If it looks like a symbol, pass symbol.
            # The inspector logic handles fallback, but let's try to be smart.
            is_path = "/" in target or target.endswith(".py") or target.endswith(".md")
            
            if is_path:
                result = inspect_entity(repo_root, path=target, include_full_source=full_source)
            else:
                result = inspect_entity(repo_root, symbol=target, include_full_source=full_source)
            
            self._render_result(result)
            
        except Exception as e:
            self._show_error(f"Inspection failed: {str(e)}")

    def _render_result(self, res: InspectionResult) -> None:
        container = self.query_one("#results-container")
        container.remove_children()
        
        # Header
        container.mount(Static(f"FILE: {res.path} ({res.source_mode})", classes="section-header"))
        
        # Summary
        summary = res.file_summary or res.enrichment.get("summary")
        if summary:
             container.mount(Static(f"[italic]{summary}[/italic]", classes="data-row"))
        
        # Defined Symbols (Brief)
        if res.defined_symbols:
            container.mount(Static("Defined Symbols:", classes="section-header"))
            lines = [f"- {s.name} ([blue]{s.type}[/blue])" for s in res.defined_symbols[:5]]
            if len(res.defined_symbols) > 5:
                lines.append(f"... ({len(res.defined_symbols)-5} more)")
            container.mount(Static("\n".join(lines), classes="data-row"))

        # Relationships
        self._render_rel_section(container, "Parents", res.parents)
        self._render_rel_section(container, "Incoming Calls", res.incoming_calls)
        self._render_rel_section(container, "Outgoing Calls", res.outgoing_calls)
        self._render_rel_section(container, "Related Tests", res.related_tests)

        # Enrichment (Pitfalls/Side Effects)
        enrich = res.enrichment
        if enrich.get("pitfalls"):
             container.mount(Static("⚠️  Pitfalls:", classes="section-header"))
             container.mount(Static(str(enrich["pitfalls"])), classes="data-row")

        # Snippet
        container.mount(Static("Source:", classes="section-header"))
        code_text = res.full_source if res.full_source else res.snippet
        container.mount(Static(code_text, classes="snippet-box"))

    def _render_rel_section(self, container: ScrollableContainer, title: str, items: list) -> None:
        if not items:
            return
        container.mount(Static(f"{title}:", classes="section-header"))
        # Display symbol or path
        lines = [f"- {x.symbol or x.path}" for x in items]
        container.mount(Static("\n".join(lines), classes="data-row"))

    def _show_error(self, msg: str) -> None:
        container = self.query_one("#results-container")
        container.remove_children()
        container.mount(Static(msg, classes="error-msg"))

    # Navigation Actions
    def action_nav_monitor(self) -> None:
        from llmc.tui.screens.monitor import MonitorScreen
        self.app.push_screen(MonitorScreen())
        
    def action_nav_search(self) -> None:
        from llmc.tui.screens.search import SearchScreen
        self.app.push_screen(SearchScreen())
        
    def action_nav_inspect(self) -> None:
        pass # Already here
