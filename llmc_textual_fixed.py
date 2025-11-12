#!/usr/bin/env python3
"""
LLMC (LLM Commander) Textual TUI - FIXED VERSION
Professional terminal interface with working navigation
"""

import sys
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label, Button, Static
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding


class MenuButton(Static):
    """A styled button widget for the menu."""
    
    def __init__(self, text: str, key: str, action: str):
        super().__init__(text)
        self.key = key
        self.action = action
        self.add_class("menu-button")
    
    def on_click(self) -> None:
        """Handle mouse click."""
        self.app.post_message(self.app.messages.Typed(self.key))


class LLMCApp(App):
    """LLMC Textual TUI Application."""
    
    CSS = """
    Screen {
        background: $surface;
        color: $text;
    }
    
    #main-container {
        align: center middle;
        height: auto;
        margin: 2;
    }
    
    #menu-box {
        width: 60;
        height: auto;
        border: solid $accent;
        padding: 2;
        background: $panel;
    }
    
    #title {
        text-align: center;
        width: 100%;
        color: $accent;
        text-style: bold;
        height: 3;
    }
    
    #subtitle {
        text-align: center;
        width: 100%;
        color: $text-muted;
        height: 2;
    }
    
    .menu-button {
        width: 100%;
        height: 3;
        margin: 0 1;
        content-align: left middle;
        background: $surface;
        border: solid $surface;
        color: $text;
    }
    
    .menu-button:hover {
        background: $accent;
        color: $text;
        border: solid $accent;
    }
    
    .menu-button:focus {
        background: $accent;
        color: $text;
        border: solid $accent;
    }
    
    .exit-button {
        background: $error;
        color: $text;
        border: solid $error;
        margin-top: 1;
    }
    
    .exit-button:hover {
        background: $error-lighten-1;
        border: $error-lighten-1;
    }
    """
    
    BINDINGS = [
        Binding("1", "key_1", "Option 1"),
        Binding("2", "key_2", "Option 2"),  
        Binding("3", "key_3", "Option 3"),
        Binding("9", "key_9", "Exit"),
        Binding("up", "focus_previous", "Previous"),
        Binding("down", "focus_next", "Next"),
        Binding("enter", "press", "Select"),
        Binding("escape", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Container(id="main-container"):
            with Container(id="menu-box"):
                yield Label("LLMC", id="title")
                yield Label("LLM Commander Terminal Interface", id="subtitle")
                
                # Main menu items
                yield MenuButton("1. 📊 Reporting Dashboards", "1", "reporting")
                yield MenuButton("2. 📚 Documentation", "2", "documentation")
                yield MenuButton("3. ⚙️ Smart Setup & Configure", "3", "setup")
                yield Label("", classes="spacer")
                yield MenuButton("9. 🚪 Exit", "9", "exit")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Set up the application."""
        self.title = "LLMC - LLM Commander Terminal Interface"
        self.sub_title = "Press numbers 1-9 or use arrows + Enter"
        
    def action_key_1(self) -> None:
        """Handle key 1 - Reporting Dashboards."""
        self.title = "LLMC - Reporting Dashboards"
        self.bell()
        # TODO: Implement reporting dashboards
    
    def action_key_2(self) -> None:
        """Handle key 2 - Documentation."""
        self.title = "LLMC - Documentation"
        self.bell()
        # TODO: Implement documentation
    
    def action_key_3(self) -> None:
        """Handle key 3 - Smart Setup."""
        self.title = "LLMC - Smart Setup & Configure"
        self.bell()
        # TODO: Implement smart setup menu
    
    def action_key_9(self) -> None:
        """Handle key 9 - Exit."""
        self.title = "LLMC - Exiting..."
        self.bell()
        self.exit()
    
    def action_focus_previous(self) -> None:
        """Focus previous button."""
        self.focus_previous()
    
    def action_focus_next(self) -> None:
        """Focus next button."""
        self.focus_next()
    
    def action_press(self) -> None:
        """Press focused button."""
        focused = self.focused
        if focused and hasattr(focused, 'action'):
            if hasattr(self, f"action_key_{focused.action}"):
                getattr(self, f"action_key_{focused.action}")()


if __name__ == "__main__":
    app = LLMCApp()
    app.run()