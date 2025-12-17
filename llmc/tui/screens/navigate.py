"""
Navigate Screen - File explorer and code viewer.
"""

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid
from textual.widgets import DirectoryTree, Static, TextArea

from llmc.tui.base import LLMCScreen


class NavigateScreen(LLMCScreen):
    """
    File navigation screen with directory tree and code preview.
    Allows browsing the repository and viewing file contents.
    """

    SCREEN_TITLE = "Navigate"

    BINDINGS = LLMCScreen.BINDINGS + [
        Binding("f", "toggle_tree", "Toggle Tree"),
        Binding("i", "inspect_file", "Inspect"),
    ]

    CSS = """
    NavigateScreen {
        layout: vertical;
        background: $surface;
    }

    #nav-grid {
        layout: grid;
        grid-size: 2 1;
        grid-columns: 30% 70%;
        grid-rows: 1fr;
        grid-gutter: 1;
        padding: 1;
        height: 1fr;
    }

    #tree-panel {
        height: 100%;
        border: heavy $primary;
        background: $surface-darken-1;
    }

    #code-panel {
        height: 100%;
        border: heavy $secondary;
        background: $surface;
    }

    DirectoryTree {
        background: $surface-darken-1;
    }

    #code-view {
        width: 100%;
        height: 100%;
        border: none;
    }

    .panel-title {
        background: $primary;
        color: $text;
        text-style: bold;
        padding: 0 1;
    }
    """

    def __init__(self):
        super().__init__()
        self.current_path: Path | None = None

    def compose_content(self) -> ComposeResult:
        """Build navigation layout."""
        repo_root = getattr(self.app, "repo_root", Path.cwd())

        with Grid(id="nav-grid"):
            # Left: File Tree
            with Container(id="tree-panel"):
                yield Static("File Explorer", classes="panel-title")
                yield DirectoryTree(repo_root, id="file-tree")

            # Right: Code View
            with Container(id="code-panel"):
                yield Static("Code Preview", classes="panel-title", id="code-title")
                # Using TextArea for code viewing (read-only)
                text_area = TextArea.code_editor(
                    "", language="python", read_only=True, id="code-view"
                )
                yield text_area

    def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Handle file selection in tree."""
        self.current_path = event.path
        self._load_file_content(event.path)

    def _load_file_content(self, path: Path) -> None:
        """Load and display file content."""
        code_view = self.query_one("#code-view", TextArea)
        title = self.query_one("#code-title", Static)

        try:
            # Update title
            rel_path = path.relative_to(getattr(self.app, "repo_root", Path.cwd()))
            title.update(f"Code Preview: {rel_path}")

            # Determine language based on extension
            ext = path.suffix.lower()
            lang = "python"  # default
            if ext in [".md", ".markdown"]:
                lang = "markdown"
            elif ext in [".json"]:
                lang = "json"
            elif ext in [".sh", ".bash"]:
                lang = "bash"
            elif ext in [".toml"]:
                lang = "toml"
            elif ext in [".css"]:
                lang = "css"
            elif ext in [".html"]:
                lang = "html"
            elif ext in [".js"]:
                lang = "javascript"

            # Load content
            content = path.read_text(encoding="utf-8")
            code_view.load_text(content)
            code_view.language = lang

        except Exception as e:
            code_view.load_text(f"Error loading file: {e}")
            title.update("Error")

    def action_toggle_tree(self) -> None:
        """Toggle tree visibility (expand code view)."""
        # TODO: Implement layout toggling if needed
        pass

    def action_inspect_file(self) -> None:
        """Open current file in Inspector."""
        if self.current_path:
            try:
                from llmc.tui.screens.inspector import InspectorScreen

                # We need to pass the path to the inspector, but InspectorScreen
                # currently takes input from user.
                # We can modify InspectorScreen or just switch and pre-fill.
                # For now, just switch and let user know.

                # Ideally, we would want to pass arguments to InspectorScreen
                # But looking at InspectorScreen code, it doesn't accept args in __init__
                # It does have 'on_mount' that focuses input.

                self.app.switch_screen(InspectorScreen())
                # Note: To fully integrate, we would need to modify InspectorScreen
                # to accept an initial path.
                self.notify(
                    f"Switching to Inspector. Please type: {self.current_path.name}"
                )

            except ImportError:
                self.notify("Inspector screen not available", severity="warning")
        else:
            self.notify("No file selected", severity="warning")
