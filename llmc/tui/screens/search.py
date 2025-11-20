#!/usr/bin/env python3
"""
Search Screen - Interactive RAG code search
"""
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Static, Input, Label, Button
from textual.message import Message


class SearchScreen(Screen):
    """Interactive code search using RAG"""
    
    CSS = """
    SearchScreen {
        layout: vertical;
    }
    
    #search-container {
        height: auto;
        padding: 1;
        border: heavy $primary;
    }
    
    #search-input {
        width: 100%;
    }
    
    #results-container {
        height: 1fr;
        border: heavy $secondary;
        padding: 1;
        margin-top: 1;
    }
    
    .status-message {
        color: $text-muted;
        text-align: center;
        margin: 2;
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
    
    .result-rank {
        color: $warning;
        text-style: bold;
    }
    
    .result-path {
        color: $accent;
        text-style: bold;
    }
    
    .result-score {
        color: $success;
    }
    
    .result-summary {
        color: $text-muted;
        margin-top: 1;
    }
    """
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("ctrl+r", "clear", "Clear"),
    ]
    
    def compose(self) -> ComposeResult:
        """Create the search interface"""
        with Vertical(id="search-container"):
            yield Label("🔍 Search Code (RAG-powered semantic search)")
            yield Input(
                placeholder="Enter search query (e.g. 'authentication logic', 'cache implementation')...",
                id="search-input"
            )
            yield Button("Search", id="search-btn", variant="primary")
        
        with ScrollableContainer(id="results-container"):
            yield Static("Enter a query and press Search or Enter to begin", classes="status-message")
    
    def on_mount(self) -> None:
        """Focus the search input when mounted"""
        self.query_one("#search-input", Input).focus()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in search input"""
        if event.input.id == "search-input":
            self.perform_search()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle search button click"""
        if event.button.id == "search-btn":
            self.perform_search()
    
    def perform_search(self) -> None:
        """Execute RAG search and display results"""
        search_input = self.query_one("#search-input", Input)
        query = search_input.value.strip()
        
        if not query:
            self.show_status("⚠️  Please enter a search query")
            return
        
        self.show_status(f"🔄 Searching for: {query}...")
        
        try:
            # Call RAG CLI
            repo_root = self.app.repo_root
            cmd = [
                "python3", "-m", "tools.rag.cli",
                "search", query,
                "--limit", "10",
                "--json"
            ]
            
            result = subprocess.run(
                cmd,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=30
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
        # Don't reuse the same ID - just use a class
        results_container.mount(Static(message, classes="status-message"))
    
    def display_results(self, results: List[Dict[str, Any]], query: str) -> None:
        """Display search results"""
        results_container = self.query_one("#results-container")
        results_container.remove_children()
        
        # Header - don't use id, just mount it
        header = Static(f"Found {len(results)} results for: [bold]{query}[/bold]\n", classes="results-header")
        results_container.mount(header)
        
        # Result items
        for result in results:
            result_widget = self.create_result_widget(result)
            results_container.mount(result_widget)
    
    def create_result_widget(self, result: Dict[str, Any]) -> Static:
        """Create a formatted result widget"""
        rank = result.get("rank", 0)
        path = result.get("path", "unknown")
        score = result.get("score", 0.0)
        symbol = result.get("symbol", "")
        lines = result.get("lines", [])
        summary = result.get("summary", "")
        
        # Format the result text
        text_parts = []
        text_parts.append(f"[yellow bold]#{rank}[/yellow bold] [cyan bold]{path}[/cyan bold]")
        
        if symbol:
            text_parts.append(f"   Symbol: [magenta]{symbol}[/magenta]")
        
        if lines:
            line_range = f"{lines[0]}-{lines[1]}" if len(lines) > 1 else str(lines[0])
            text_parts.append(f"   Lines: {line_range}")
        
        text_parts.append(f"   Score: [green]{score:.4f}[/green]")
        
        if summary:
            text_parts.append(f"\n   [dim]{summary}[/dim]")
        
        result_text = "\n".join(text_parts)
        return Static(result_text, classes="result-item")
    
    def action_clear(self) -> None:
        """Clear search and results"""
        self.query_one("#search-input", Input).value = ""
        self.show_status("Enter a query and press Search or Enter to begin")
        self.query_one("#search-input", Input).focus()
