#!/usr/bin/env python3
"""
LLMC TUI - Cyberpunk Terminal Interface

The visual frontend to the LLMC CLI. Every CLI command has a corresponding
TUI screen. Same logic, different interface.

Launch with: llmc tui
"""

from pathlib import Path
import sys

from textual.app import App
from textual.binding import Binding

from llmc.tui.screens.dashboard import DashboardScreen
from llmc.tui.theme import GLOBAL_CSS


class LLMC_TUI(App):
    """
    Main LLMC TUI Application.
    
    Navigation:
        1 - Dashboard (stats, quick actions, logs)
        2 - Search (code search)
        3 - Service (daemon control)
        4 - Navigate (where-used, lineage)
        5 - Docs (documentation generation)
        6 - RUTA (user testing)
        7 - Analytics (query stats)
        8 - Config (enrichment editor)
        q - Quit
    """

    TITLE = "LLMC"
    SUB_TITLE = "Cyberpunk Console"
    CSS = GLOBAL_CSS

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(self, repo_root: Path | None = None):
        super().__init__()
        self.repo_root = repo_root or Path.cwd()

    def on_mount(self) -> None:
        """Start on the dashboard."""
        self.push_screen(DashboardScreen())


def main():
    """Entry point for the TUI."""
    # Parse args
    repo_root = Path.cwd()
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ("-h", "--help"):
            print(__doc__)
            print("\nUsage: llmc-tui [repo_path]")
            print("  repo_path: Path to repository (default: current directory)")
            return
        repo_root = Path(arg).resolve()
    
    if not repo_root.exists():
        print(f"Error: Path does not exist: {repo_root}")
        sys.exit(1)
    
    # Launch TUI
    app = LLMC_TUI(repo_root=repo_root)
    app.run()


if __name__ == "__main__":
    main()
