#!/usr/bin/env python3
"""
LLMC Debug Version - Help identify TUI issues
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label
from textual.binding import Binding
import sys


class DebugApp(App):
    """Debug version to see what's happening."""
    
    BINDINGS = [
        Binding("1", "debug_1", "Debug 1"),
        Binding("2", "debug_2", "Debug 2"),
        Binding("escape", "quit", "Quit"),
    ]
    
    def compose(self) -> ComposeResult:
        print("🔍 DEBUG: compose() called", file=sys.stderr)
        yield Header()
        
        yield Label("🔍 LLMC DEBUG MODE", markup=False)
        yield Label(f"Python: {sys.version}", markup=False)
        yield Label(f"Textual: {self.app._driver.__class__.__name__ if hasattr(self.app, '_driver') else 'No driver'}", markup=False)
        yield Label("", markup=False)
        yield Label("KEY BINDINGS TEST:", markup=False)
        yield Label("Press 1, 2, or ESC", markup=False)
        yield Label("", markup=False)
        yield Label("Current bindings: 1, 2, escape", markup=False)
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Debug mount."""
        print("🔍 DEBUG: on_mount() called", file=sys.stderr)
        self.title = "LLMC Debug"
    
    def action_debug_1(self) -> None:
        """Debug action 1."""
        print("✅ DEBUG: Key 1 pressed - action_debug_1() called", file=sys.stderr)
        self.bell()
        self.title = "Key 1 pressed!"
    
    def action_debug_2(self) -> None:
        """Debug action 2."""
        print("✅ DEBUG: Key 2 pressed - action_debug_2() called", file=sys.stderr)
        self.bell()
        self.title = "Key 2 pressed!"
    
    def action_quit(self) -> None:
        """Debug quit."""
        print("🔍 DEBUG: Quit action called", file=sys.stderr)
        self.exit()


if __name__ == "__main__":
    print("🔍 Starting LLMC Debug TUI...")
    print("Check console output for debug messages", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    
    app = DebugApp()
    try:
        app.run()
    except Exception as e:
        print(f"❌ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)