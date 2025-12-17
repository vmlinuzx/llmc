#!/usr/bin/env python3
"""
Search Screen - Interactive RAG code search

Maps to: llmc search <query>
"""

import json
from pathlib import Path
import subprocess
from typing import Any

from textual import events
from textual.app import ComposeResult
from textual.containers import Container, Grid, ScrollableContainer
from textual.message import Message
from textual.widgets import Button, Input, Static

from llmc.tui.base import LLMCScreen


class ResultSelected(Message):
    """Message emitted when a result item is clicked."""

    def __init__(self, sender, result: dict[str, Any]) -> None:
        self.result = result
        super().__init__()


def _format_result_text(result: dict[str, Any]) -> str:
    """Render a result summary block."""
    rank = result.get("rank", 0)
    path = result.get("path", "unknown")
    score = float(result.get("score", 0.0) or 0.0)
    symbol = result.get("symbol", "")
    lines = result.get("lines", [])
    summary = result.get("summary", "")
    metadata = result.get("metadata", result.get("meta", {})) or {}
    relations = metadata.get("relations") or result.get("relations") or []

    norm_score = float(result.get("normalized_score", 0.0) or 0.0)

    text_parts = []
    text_parts.append(f"[yellow bold]#{rank}[/yellow bold] [cyan bold]{path}[/cyan bold]")

    if symbol:
        text_parts.append(f"   Symbol: [magenta]{symbol}[/magenta]")

    if lines:
        line_range = f"{lines[0]}-{lines[1]}" if len(lines) > 1 else str(lines[0])
        text_parts.append(f"   Lines: {line_range}")

    text_parts.append(f"   Score: [green]{norm_score:.1f}[/green] [dim]({score:.4f})[/dim]")

    if summary:
        text_parts.append(f"\n   [dim]{summary}[/dim]")

    if relations:
        rel_lines = []
        for rel in relations[:3]:
            rel_lines.append(f"   • {rel}")
        text_parts.append("\nRelations:\n" + "\n".join(rel_lines))

    return "\n".join(text_parts)


class ResultWidget(Static):
    """Clickable result block."""

    def __init__(self, result: dict[str, Any]) -> None:
        super().__init__(_format_result_text(result), classes="result-item", expand=True)
        self.result = result

    def on_click(self, _: events.Click) -> None:
        self.post_message(ResultSelected(self, self.result))


class SearchScreen(LLMCScreen):
    """Interactive code search using RAG - maps to 'llmc search'"""

    SCREEN_TITLE = "Search"

    def _format_entity_id(self, entity_id: str) -> str:
        """Formats internal entity ID to human-readable string, handling prefixes like 'Extends: '."""
        # Handle "Extends: type:some_id" or "Calls: type:some_id"
        if ": " in entity_id and entity_id.split(": ", 1)[0] in ("Extends", "Calls"):
            prefix, actual_id = entity_id.split(": ", 1)
            return f"{prefix}: {self._format_entity_id(actual_id)}"

        if ":" in entity_id:
            kind, name = entity_id.split(":", 1)
            # For 'type' and 'sym', strip module path
            if kind in ("type", "sym"):
                return name.rsplit(".", 1)[-1]
            return name
        return entity_id

    CSS = """
    SearchScreen {
        layout: vertical;
        padding: 1;
        background: $surface;
    }

    #header {
        height: 3;
        border: heavy $primary;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }

    #search-grid {
        layout: grid;
        grid-size: 2 1;
        grid-columns: 42% 58%;
        grid-rows: 1fr;
        grid-gutter: 1;
        height: 1fr;
    }

    .panel {
        border: heavy $secondary;
        padding: 1;
        background: $surface;
    }

    #left-column {
        layout: vertical;
        height: 1fr;
    }

    #query-panel {
        height: 1fr;
        margin-bottom: 1;
    }

    #results-panel {
        height: 3fr;
    }

    #right-column {
        layout: vertical;
        height: 1fr;
    }

    #details-panel {
        height: 1fr;
    }

    #query-input {
        width: 100%;
        margin-bottom: 1;
    }

    .panel-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .status-message {
        color: $text-muted;
        text-align: left;
        margin: 0;
    }

    .results-header {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }

    .result-item {
        margin: 1 0;
        padding: 1;
        border: solid $accent;
        background: $surface-darken-1;
    }

    .result-item:hover {
        border: heavy $accent;
        background: $boost;
    }

    .result-summary {
        color: $text-muted;
        margin-top: 1;
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
    """

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("ctrl+r", "clear", "Clear"),
        ("enter", "search", "Search"),
        ("1", "nav_monitor", "Monitor"),
        ("2", "nav_search", "Search"),
    ]

    def __init__(self):
        super().__init__()
        self.menu_items = [
            ("1", "Monitor System", self.action_nav_monitor),
            ("2", "Search Code", self.action_nav_search),
        ]

    def compose(self) -> ComposeResult:
        """Create the search interface"""
        yield Static("LLMC Search", id="header")

        with Grid(id="search-grid"):
            with Container(id="left-column"):
                with Container(id="query-panel", classes="panel"):
                    yield Input(
                        placeholder="Enter search query (e.g. 'authentication logic', 'cache implementation')...",
                        id="query-input",
                    )
                    yield Button("Search (Enter)", id="search-btn", variant="primary")

                with Container(id="results-panel", classes="panel"):
                    yield Static("Results + Context", classes="panel-title")
                    with ScrollableContainer(id="results-container"):
                        yield Static(
                            "Enter a query and press Search or Enter to begin",
                            classes="status-message",
                        )

            with Container(id="right-column"):
                with Container(id="details-panel", classes="panel"):
                    yield Static("Details", classes="panel-title")
                    with ScrollableContainer(id="details-body"):
                        yield Static(
                            "\n".join(
                                [
                                    "Click a result to load its snippet here.",
                                    "Shows lines around the hit plus relations/summary.",
                                ]
                            ),
                            classes="status-message",
                        )

        yield Static("[esc] Back   [enter] Search   [ctrl+r] Clear", id="footer")

    def on_mount(self) -> None:
        """Focus the search input when mounted"""
        self.query_one("#header", Static).update(f"LLMC Search :: repo {self.app.repo_root}")
        self.query_one("#query-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in search input"""
        if event.input.id == "query-input":
            self.perform_search()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle search button click and menu clicks."""
        if event.button.id == "search-btn":
            self.perform_search()
            return

        btn_id = event.button.id or ""
        mapping = {
            "menu-1": self.action_nav_monitor,
            "menu-2": self.action_nav_search,
        }
        handler = mapping.get(btn_id)
        if handler:
            handler()

    def action_search(self) -> None:
        """Trigger search via Enter binding."""
        self.perform_search()

    def perform_search(self) -> None:
        """Execute RAG search and display results"""
        search_input = self.query_one("#query-input", Input)
        query = search_input.value.strip()

        if not query:
            self.show_status("⚠️  Please enter a search query")
            return

        self.show_status(f"🔄 Searching for: {query}...")

        try:
            # Call RAG CLI
            repo_root = self.app.repo_root
            cmd = [
                "python3",
                "-m",
                "llmc.rag.cli",
                "search",
                query,
                "--limit",
                "20",
                "--json",
                "--debug",
            ]

            result = subprocess.run(
                cmd, check=False, cwd=repo_root, capture_output=True, text=True, timeout=30
            )

            if result.returncode != 0:
                self.show_status(f"❌ Search failed: {result.stderr}")
                return

            # Parse results
            results = json.loads(result.stdout)

            if not results:
                self.show_status(f"No results found for: {query}")
                return

            # Display results
            self.display_results(results, query)

        except subprocess.TimeoutExpired:
            self.show_status("⏱️  Search timed out")
        except json.JSONDecodeError as e:
            self.show_status(f"❌ Failed to parse results: {e}")
        except Exception as e:
            self.show_status(f"❌ Error: {e}")

    def show_status(self, message: str) -> None:
        """Show status message in results area"""
        results_container = self.query_one("#results-container")
        results_container.remove_children()
        results_container.mount(Static(message, classes="status-message"))

    def display_results(self, results: list[dict[str, Any]], query: str) -> None:
        """Display search results"""
        results_container = self.query_one("#results-container")
        results_container.remove_children()

        header = Static(
            f"Found {len(results)} results for: [bold]{query}[/bold]\n", classes="results-header"
        )
        results_container.mount(header)

        for result in results:
            result_widget = self.create_result_widget(result)
            results_container.mount(result_widget)

        # Reset details panel prompt for new result set
        self.update_details("Click a result to load its snippet here.")

    def create_result_widget(self, result: dict[str, Any]) -> Static:
        """Create a clickable result widget."""
        return ResultWidget(result)

    def action_clear(self) -> None:
        """Clear search and results"""
        self.query_one("#query-input", Input).value = ""
        self.show_status("Enter a query and press Search or Enter to begin")
        self.query_one("#query-input", Input).focus()
        self.update_details("Click a result to load its snippet here.")

    def on_result_selected(self, message: ResultSelected) -> None:
        """Handle result selection and render snippet in the details pane."""
        result = message.result
        detail_text = self.build_detail_text(result)
        self.update_details(detail_text)

    def build_detail_text(self, result: dict[str, Any]) -> str:
        """Build detailed view with snippet and relations."""
        path = result.get("path", "unknown")
        symbol = result.get("symbol", "")
        lines = result.get("lines", [])
        debug = result.get("debug") or {}

        parts = []

        # Header
        parts.append(f"[bold cyan]{path}[/bold cyan]")
        graph_info = debug.get("graph") or {}
        node_type = graph_info.get("node_type", "unknown")
        line_str = f"{lines[0]}-{lines[1]}" if len(lines) > 1 else str(lines[0]) if lines else "?"
        parts.append(
            f"Symbol: [magenta]{symbol}[/magenta] ([blue]{node_type}[/blue])  Span: {line_str}"
        )
        parts.append("")

        # Search
        search_info = debug.get("search", {})
        norm_score = float(result.get("normalized_score", 0.0) or 0.0)
        parts.append("[bold]Search[/bold]")
        parts.append(f"  Rank:       #{search_info.get('rank', '?')}")
        parts.append(
            f"  Score:      [green]{norm_score:.1f}[/green] ({search_info.get('score', 0.0):.4f})"
        )
        if "embedding_similarity" in search_info:
            parts.append(f"  Embedding:  {search_info['embedding_similarity']:.4f}")
        parts.append("")

        # Graph
        graph_info = debug.get("graph")
        parts.append("[bold]Graph[/bold]")
        if graph_info:
            if graph_info.get("parents"):
                parts.append("  Parents:")
                for p in graph_info["parents"]:
                    parts.append(f"    - {self._format_entity_id(p)}")

            if graph_info.get("children"):
                parts.append("  Children:")
                for c in graph_info["children"]:
                    parts.append(f"    - {self._format_entity_id(c)}")

            if graph_info.get("related_code"):
                parts.append("  Related code:")
                for r in graph_info["related_code"]:
                    parts.append(f"    - {r}")

            if graph_info.get("related_tests"):
                parts.append("  Related tests:")
                for r in graph_info["related_tests"]:
                    parts.append(f"    - {r}")
        else:
            parts.append("  (no graph data)")
        parts.append("")

        # Enrichment
        enrich = debug.get("enrichment")
        parts.append("[bold]Enrichment[/bold]")

        def _format_list_field(val: Any) -> str | None:
            if not val:
                return None
            if val == "[]":
                return None

            generic_placeholders = {"params", "returns", "args", "kwargs", "none"}

            if isinstance(val, list):
                # Filter out generic placeholders and format
                filtered_list = [str(x) for x in val if str(x).lower() not in generic_placeholders]
                if not filtered_list:
                    return None
                return ", ".join(filtered_list)

            if isinstance(val, str) and val.lower() in generic_placeholders:
                return None

            return str(val)

        if enrich:
            if enrich.get("summary"):
                parts.append(f"  Summary:   [dim]{enrich['summary']}[/dim]")

            inputs = _format_list_field(enrich.get("inputs"))
            if inputs:
                parts.append(f"  Inputs:    {inputs}")

            outputs = _format_list_field(enrich.get("outputs"))
            if outputs:
                parts.append(f"  Outputs:   {outputs}")

            side_effects = _format_list_field(enrich.get("side_effects"))
            if side_effects:
                parts.append(f"  Side Effects: {side_effects}")

            pitfalls = _format_list_field(enrich.get("pitfalls"))
            if pitfalls:
                parts.append(f"  Pitfalls:  {pitfalls}")

            parts.append(f"  Evidence:  {enrich.get('evidence_count', 0)} spans")
        else:
            parts.append("  (none)")
        parts.append("")

        # Provenance
        prov = debug.get("provenance", {})
        parts.append("[bold]Provenance[/bold]")
        parts.append(f"  Kind:       {prov.get('kind', result.get('kind', 'unknown'))}")
        if prov.get("last_commit"):
            parts.append(f"  Commit:     {prov['last_commit']}")
        parts.append("")

        # Snippet
        snippet = self.get_snippet(path, lines)
        parts.append("[bold]Snippet[/bold]")
        parts.append(snippet)

        return "\n".join(parts)

    def get_snippet(self, path: str, lines: list[int], context: int = 3) -> str:
        """Load a line span from disk with padding context."""
        try:
            file_path = Path(path)
            if not file_path.is_absolute():
                file_path = (Path(self.app.repo_root) / path).resolve()
            if not file_path.exists():
                return f"[red]File not found[/red]: {file_path}"

            file_lines = file_path.read_text().splitlines()
            if lines:
                start = max(1, lines[0] - context)
                end_line = lines[1] if len(lines) > 1 else lines[0]
                end = min(len(file_lines), end_line + context)
            else:
                start, end = 1, min(len(file_lines), 80)

            snippet_lines = file_lines[start - 1 : end]
            numbered = [f"{i:>5} | {line}" for i, line in enumerate(snippet_lines, start=start)]
            return "\n".join(numbered)
        except Exception as exc:
            return f"[red]Error reading file[/red]: {exc}"

    def update_details(self, text: str) -> None:
        """Update the details pane."""
        details = self.query_one("#details-body", ScrollableContainer)
        details.remove_children()
        details.mount(Static(text))

    def action_nav_monitor(self) -> None:
        """Go to the monitor screen."""
        try:
            from llmc.tui.screens.monitor import MonitorScreen

            self.app.push_screen(MonitorScreen())
        except Exception as exc:
            self.show_status(f"❌ Cannot open monitor: {exc}")

    def action_nav_search(self) -> None:
        """Stay on search screen (noop)."""
        self.show_status("Already on Search")
