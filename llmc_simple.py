#!/usr/bin/env python3
"""
LLMC (LLM Commander) Textual TUI - SIMPLE WORKING VERSION
Just focus on single-key navigation that actually works
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label
from textual.containers import Container, Vertical
from textual.binding import Binding
import time


class LLMCApp(App):
    """LLMC Simple TUI - Focus on working single-key navigation."""
    
    CSS = """
    Screen {
        background: $surface;
        align: center middle;
    }
    
    .menu-container {
        width: 80%;
        height: auto;
        border: solid $accent;
        padding: 3;
        background: $panel;
    }
    
    .title {
        text-align: center;
        color: $accent;
        text-style: bold;
        height: 3;
    }
    
    .option {
        height: 3;
        background: $surface;
        margin: 0 1;
        content-align: left middle;
        border: solid $surface;
    }
    
    .option:hover {
        background: $accent;
        color: $text;
    }
    
    .option.selected {
        background: $accent;
        color: $text;
    }
    
    .hint {
        text-align: center;
        color: $text-muted;
        height: 2;
        margin-top: 1;
    }
    """
    
    BINDINGS = [
        Binding("1", "option_1", "Reporting"),
        Binding("2", "option_2", "Documentation"),
        Binding("3", "option_3", "Smart Setup"),
        Binding("9", "quit", "Exit"),
        Binding("escape", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Vertical(classes="menu-container"):
            yield Label("🏢 LLMC", classes="title")
            yield Label("LLM Commander Terminal Interface", classes="title")
            yield Label("", classes="spacer")
            
            yield Label("1. 📊 Reporting Dashboards", classes="option")
            yield Label("2. 📚 Documentation", classes="option")
            yield Label("3. ⚙️ Smart Setup & Configure", classes="option")
            yield Label("", classes="spacer")
            yield Label("9. 🚪 Exit", classes="option")
            
            yield Label("Press 1, 2, 3, or 9 • ESC to quit", classes="hint")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Initialize app."""
        self.title = "LLMC - LLM Commander"
    
    def action_option_1(self) -> None:
        """Handle Reporting Dashboards."""
        self.title = "LLMC - Reporting Dashboards"
        self.bell()  # Sound feedback
        time.sleep(0.5)  # Brief delay for feedback
        # TODO: Implement actual reporting dashboards
        print("Opening Reporting Dashboards...")
        # Reset title
        self.title = "LLMC - LLM Commander"
    
    def action_option_2(self) -> None:
        """Handle Documentation."""
        self.title = "LLMC - Documentation"
        self.bell()
        time.sleep(0.5)
        print("Opening Documentation...")
        self.title = "LLMC - LLM Commander"
    
    def action_option_3(self) -> None:
        """Handle Smart Setup."""
        self.title = "LLMC - Smart Setup & Configure"
        self.bell()
        time.sleep(0.5)
        print("Opening Smart Setup...")
        self.title = "LLMC - LLM Commander"
    
    def action_quit(self) -> None:
        """Exit the application."""
        self.bell()
        self.exit()


if __name__ == "__main__":
    print("🚀 Starting LLMC Textual TUI...")
    print("🎯 Press 1, 2, 3, or 9 for instant navigation!")
    print("Press ESC to quit")
    print("=" * 50)
    
    app = LLMCApp()
    app.run()