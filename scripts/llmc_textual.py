#!/usr/bin/env python3
"""
LLMC (LLM Commander) Textual TUI
Professional terminal interface for LLM Commander operations
"""

import sys
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label, Button
from textual.containers import Container, Vertical
from textual.binding import Binding


class MainMenu(Container):
    """Main menu container with clean, professional layout."""
    
    def compose(self) -> ComposeResult:
        with Vertical(classes="menu-container"):
            yield Label("LLMC", id="title", classes="title")
            yield Label("LLM Commander Terminal Interface", id="subtitle", classes="subtitle")
            yield Label("", id="spacer1")
            
            # Main menu options
            yield Button("1. 📊 Reporting Dashboards", id="reporting", classes="menu-button")
            yield Button("2. 📚 Documentation", id="documentation", classes="menu-button")
            yield Button("3. ⚙️ Smart Setup & Configure", id="setup", classes="menu-button")
            yield Label("", id="spacer2")
            yield Button("9. 🚪 Exit", id="exit", classes="menu-button exit-button")


class SmartSetupMenu(Container):
    """Smart Setup sub-menu with all configuration options."""
    
    def compose(self) -> ComposeResult:
        with Vertical(classes="menu-container"):
            yield Label("Smart Setup & Configure", id="title", classes="title")
            yield Label("Choose a configuration option:", id="subtitle", classes="subtitle")
            yield Label("", id="spacer1")
            
            yield Button("1. 📁 Path Configuration", id="path-config", classes="menu-button")
            yield Button("2. 🚀 Deploy to new Repo", id="deploy", classes="menu-button")
            yield Button("3. ✅ Test Deployment", id="test-deploy", classes="menu-button")
            yield Button("4. 📋 View Configuration", id="view-config", classes="menu-button")
            yield Button("5. 🔧 Advanced Setup", id="advanced", classes="menu-button")
            yield Button("6. 💾 Backup and Restore", id="backup", classes="menu-button")
            yield Label("", id="spacer2")
            yield Button("7. ↩️ Back to Main Menu", id="back", classes="menu-button back-button")


class LLMCApp(App):
    """LLMC Textual TUI Application."""
    
    CSS = """
    Screen {
        background: $surface 0%;
        color: $text;
    }
    
    .menu-container {
        align: center middle;
        width: 80%;
        height: auto;
        border: solid $accent;
        padding: 2;
        margin: 1;
        background: $panel;
    }
    
    #title {
        text-align: center;
        width: 100%;
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }
    
    #subtitle {
        text-align: center;
        width: 100%;
        color: $text-muted;
        margin-bottom: 2;
    }
    
    .menu-button {
        width: 100%;
        height: 3;
        margin: 1 0;
        text-align: left;
        color: $text;
        background: $surface;
        border: solid $surface;
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
        margin-top: 2;
    }
    
    .exit-button:hover {
        background: $error-lighten-1;
        border: $error-lighten-1;
    }
    
    .back-button {
        background: $warning;
        color: $text;
        border: solid $warning;
        margin-top: 2;
    }
    
    .back-button:hover {
        background: $warning-lighten-1;
        border: $warning-lighten-1;
    }
    
    #spacer1, #spacer2 {
        height: 1;
    }
    """
    
    BINDINGS = [
        Binding("1", "reporting", "Reporting Dashboards"),
        Binding("2", "documentation", "Documentation"),
        Binding("3", "setup", "Smart Setup"),
        Binding("9", "quit", "Exit"),
        Binding("escape", "back", "Back"),
    ]
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield MainMenu(id="main-menu")
        yield SmartSetupMenu(id="setup-menu")
        yield Footer()
    
    def on_mount(self) -> None:
        """Set initial focus and show welcome message."""
        self.title = "LLMC - LLM Commander Terminal Interface"
        self.sub_title = "Professional Development Environment"
        # Ensure only main menu is visible initially
        self.show_main_menu()
    
    def action_reporting(self) -> None:
        """Handle Reporting Dashboards (key 1)."""
        self.show_reporting_dashboards()
    
    def action_documentation(self) -> None:
        """Handle Documentation (key 2)."""
        self.show_documentation()
    
    def action_setup(self) -> None:
        """Handle Smart Setup & Configure (key 3)."""
        self.show_setup_menu()
    
    def action_quit(self) -> None:
        """Exit the application (key 9)."""
        self.exit()
    
    def action_back(self) -> None:
        """Go back to main menu (ESC)."""
        self.show_main_menu()
    
    def action_path_config(self) -> None:
        """Handle Path Configuration in Smart Setup (key 1)."""
        self.handle_path_config()
    
    def action_deploy(self) -> None:
        """Handle Deploy to new Repo in Smart Setup (key 2)."""
        self.handle_deploy()
    
    def action_test_deploy(self) -> None:
        """Handle Test Deployment in Smart Setup (key 3)."""
        self.handle_test_deploy()
    
    def action_view_config(self) -> None:
        """Handle View Configuration in Smart Setup (key 4)."""
        self.handle_view_config()
    
    def action_advanced(self) -> None:
        """Handle Advanced Setup in Smart Setup (key 5)."""
        self.handle_advanced_setup()
    
    def action_backup(self) -> None:
        """Handle Backup and Restore in Smart Setup (key 6)."""
        self.handle_backup_restore()
    
    def show_main_menu(self) -> None:
        """Show the main menu."""
        self.query_one("#main-menu").visible = True
        self.query_one("#setup-menu").visible = False
        # Focus first menu item
        self.query_one("#reporting").focus()
    
    def show_setup_menu(self) -> None:
        """Show the Smart Setup menu."""
        self.query_one("#main-menu").visible = False
        self.query_one("#setup-menu").visible = True
        # Focus first menu item
        self.query_one("#path-config").focus()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        
        if button_id == "reporting":
            self.show_reporting_dashboards()
        elif button_id == "documentation":
            self.show_documentation()
        elif button_id == "setup":
            self.show_setup_menu()
        elif button_id == "exit":
            self.action_quit()
        elif button_id == "path-config":
            self.handle_path_config()
        elif button_id == "deploy":
            self.handle_deploy()
        elif button_id == "test-deploy":
            self.handle_test_deploy()
        elif button_id == "view-config":
            self.handle_view_config()
        elif button_id == "advanced":
            self.handle_advanced_setup()
        elif button_id == "backup":
            self.handle_backup_restore()
        elif button_id == "back":
            self.show_main_menu()
    
    def handle_path_config(self) -> None:
        """Handle Path Configuration option."""
        self.bell()  # Simple feedback
        self.title = "LLMC - Path Configuration"
        # TODO: Implement path configuration logic
    
    def handle_deploy(self) -> None:
        """Handle Deploy to new Repo option."""
        self.bell()
        self.title = "LLMC - Deploy to Repository"
        # TODO: Implement deployment logic
    
    def handle_test_deploy(self) -> None:
        """Handle Test Deployment option."""
        self.bell()
        self.title = "LLMC - Test Deployment"
        # TODO: Implement test logic
    
    def handle_view_config(self) -> None:
        """Handle View Configuration option."""
        self.bell()
        self.title = "LLMC - View Configuration"
        # TODO: Implement view logic
    
    def handle_advanced_setup(self) -> None:
        """Handle Advanced Setup option."""
        self.bell()
        self.title = "LLMC - Advanced Setup"
        # TODO: Implement advanced logic
    
    def handle_backup_restore(self) -> None:
        """Handle Backup and Restore option."""
        self.bell()
        self.title = "LLMC - Backup and Restore"
        # TODO: Implement backup logic
    
    def show_reporting_dashboards(self) -> None:
        """Show Reporting Dashboards section."""
        self.bell()
        self.title = "LLMC - Reporting Dashboards"
        # TODO: Implement reporting dashboards (future feature)
    
    def show_documentation(self) -> None:
        """Show Documentation section."""
        self.bell()
        self.title = "LLMC - Documentation"
        # TODO: Implement documentation viewer


if __name__ == "__main__":
    app = LLMCApp()
    app.run()