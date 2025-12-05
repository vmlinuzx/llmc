"""
LLMC TUI Theme - Cyberpunk aesthetic styling.

Provides:
- GLOBAL_CSS: Application-wide CSS
- LOGO_SMALL: Compact ASCII art logo
"""

# Compact logo for headers
LOGO_SMALL = """╔═══╗
║LMC║
╚═══╝"""

# Global CSS applied to the entire TUI
GLOBAL_CSS = """
Screen {
    background: #0a0a0f;
}

Header {
    background: #1a1a2e;
    color: #00ff9f;
    border: heavy #00b8ff;
    height: 3;
}

Footer {
    background: #1a1a2e;
    color: #00ff9f;
}

.nav-bar {
    height: 3;
    background: #1a1a2e;
    border: heavy #00b8ff;
    padding: 0 1;
    dock: bottom;
}

.panel {
    background: #1a1a2e;
    border: heavy #00b8ff;
    border-title-color: #00ff9f;
    border-title-style: bold;
    padding: 0 1;
}

Button {
    background: #2a2a4e;
    color: #00ff9f;
    border: solid #00b8ff;
}

Button:hover {
    background: #3a3a6e;
    border: solid #00ff9f;
}

Button.-primary {
    background: #1a4a2e;
}

Button.-error {
    background: #4a1a1a;
    color: #ff6666;
}

Input {
    background: #0a0a0f;
    border: solid #00b8ff;
    color: #ffffff;
}

Input:focus {
    border: solid #00ff9f;
}

DataTable {
    background: #0a0a0f;
}

DataTable > .datatable--header {
    background: #1a1a2e;
    color: #00ff9f;
    text-style: bold;
}

DataTable > .datatable--cursor {
    background: #2a2a4e;
    color: #ffffff;
}

Tree {
    background: #0a0a0f;
}

Tree > .tree--guides {
    color: #333344;
}

Tree > .tree--cursor {
    background: #2a2a4e;
}

ScrollableContainer {
    scrollbar-background: #1a1a2e;
    scrollbar-color: #00b8ff;
    scrollbar-color-hover: #00ff9f;
    scrollbar-color-active: #00ff9f;
}
"""


def format_status(status: str) -> str:
    """Format a status string with appropriate color."""
    status_upper = status.upper()
    if status_upper in ("ONLINE", "OK", "RUNNING", "ACTIVE"):
        return f"[bold green]{status}[/]"
    elif status_upper in ("OFFLINE", "ERROR", "STOPPED", "FAILED"):
        return f"[bold red]{status}[/]"
    elif status_upper in ("WARN", "WARNING", "PENDING"):
        return f"[yellow]{status}[/]"
    return status
