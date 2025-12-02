#!/usr/bin/env python3
"""
LLMC TUI - Main Application
A cyberpunk-styled terminal UI for LLMC
"""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from llmc.tui.screens.config import ConfigScreen
from llmc.tui.screens.inspector import InspectorScreen

# Import our custom screens
from llmc.tui.screens.monitor import MonitorScreen
from llmc.tui.screens.search import SearchScreen


class MenuScreen(Screen):
    """Main menu screen with navigation options"""

    BINDINGS = [
        Binding("1", "show_monitor", "Monitor System"),
        Binding("2", "show_search", "Search Code"),
        Binding("3", "show_inspect", "Inspect Entity"),
        Binding("4", "show_config", "Configuration"),
        Binding("5", "show_rag_doctor", "RAG Doctor"),
        Binding("q", "quit", "Quit"),
    ]

    CSS = """
    MenuScreen {
        align: center middle;
    }
    
    #menu-container {
        width: 60;
        height: auto;
        border: heavy $primary;
        background: $surface;
        padding: 2 4;
    }
    
    #title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 2;
    }
    
    .menu-item {
        width: 100%;
        height: 3;
        margin: 1 0;
        border: solid $secondary;
    }
    
    .menu-item:hover {
        border: heavy $accent;
        background: $boost;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="menu-container"):
            yield Static("LLMC - Cyberpunk Console", id="title")
            with ScrollableContainer(id="menu-scroll"):
                yield Button("[1] Monitor System", id="btn-monitor", classes="menu-item")
                yield Button("[2] Search Code", id="btn-search", classes="menu-item")
                yield Button("[3] Inspect Entity", id="btn-inspect", classes="menu-item")
                yield Button("[4] Configuration", id="btn-config", classes="menu-item")
                yield Button("[5] RAG Doctor", id="btn-rag-doctor", classes="menu-item")
            yield Static("\nPress number keys or click buttons to navigate", id="help-text")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks"""
        if event.button.id == "btn-monitor":
            self.action_show_monitor()
        elif event.button.id == "btn-search":
            self.action_show_search()
        elif event.button.id == "btn-inspect":
            self.action_show_inspect()
        elif event.button.id == "btn-config":
            self.action_show_config()
        elif event.button.id == "btn-rag-doctor":
            self.action_show_rag_doctor()

    def action_show_monitor(self) -> None:
        """Switch to monitor screen"""
        self.app.push_screen(MonitorScreen())

    def action_show_search(self) -> None:
        """Switch to search screen"""
        self.app.push_screen(SearchScreen())

    def action_show_inspect(self) -> None:
        """Switch to inspector screen"""
        self.app.push_screen(InspectorScreen())

    def action_show_config(self) -> None:
        """Switch to configuration screen"""
        self.app.push_screen(ConfigScreen())

    def action_show_rag_doctor(self) -> None:
        """Switch to RAG Doctor screen"""
        from llmc.tui.screens.rag_doctor import RAGDoctorScreen

        self.app.push_screen(RAGDoctorScreen())

    def action_quit(self) -> None:
        """Quit the application"""
        self.app.exit()


class LLMC_TUI(App):
    """Main LLMC TUI Application"""

    TITLE = "LLMC - Large Language Model Controller"
    SUB_TITLE = "Cyberpunk Console"

    CSS = """
    Screen {
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self, repo_root: Path = None):
        super().__init__()
        self.repo_root = repo_root or Path.cwd()

    def on_mount(self) -> None:
        """Initialize the app"""
        # Start on the monitor screen but keep the menu as the previous page so ESC
        # returns to navigation instead of quitting immediately.
        self.push_screen(MenuScreen())
        self.push_screen(MonitorScreen())


def main():
    """Entry point for the TUI"""
    from pathlib import Path
    import sys

    # Determine repo root
    if len(sys.argv) > 1:
        repo_root = Path(sys.argv[1]).resolve()
    else:
        repo_root = Path.cwd()

    app = LLMC_TUI(repo_root=repo_root)
    app.run()


if __name__ == "__main__":
    main()
