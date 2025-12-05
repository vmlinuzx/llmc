# LLMC TUI Style Guide

## Overview

This document defines the visual and interaction standards for the LLMC TUI (Text User Interface). All screens must follow these standards to maintain consistency.

## Header

**Always use the Textual `Header` widget.**

- Title: `LARGE LANGUAGE MODEL COMPRESSOR` (centered)
- Subtitle: Empty (no screen-specific hints in header)
- Background: `#1a1a2e`
- Text color: `#00ff9f` (neon green)
- Border: `solid #00b8ff` (cyan)

```css
Header {
    background: #1a1a2e;
    color: #00ff9f;
    border: solid #00b8ff;
}
```

The header is **static across all screens**. Do not modify the title or add per-screen content.

## Footer (Navigation Bar)

The navigation bar is a `Static` widget docked to the bottom with the menu items.

**Format:**
```
(1)Dashboard  (2)Search  (3)Service  (4)Nav  (5)Docs  (6)RUTA  (7)Analytics  (8)Config  (esc)Back  (q)Quit
```

**Styling:**
- Hotkeys: `[yellow](x)[/]` format
- Labels: `[#00ff9f]Label[/]` format
- Background: `#1a1a2e`
- Border: `border-top: solid #00b8ff`

```css
.nav-bar {
    height: 1;
    background: #1a1a2e;
    border-top: solid #00b8ff;
    padding: 0 1;
    dock: bottom;
}
```

The footer is **static across all screens**. Never modify the nav bar content.

## Panels

Use `Container` with the `.panel` class and `border_title` for panel labels.

```python
panel = Container(id="my-panel", classes="panel")
panel.border_title = "Panel Title"
```

**CSS:**
```css
.panel {
    background: #1a1a2e;
    border: heavy #00b8ff;
    border-title-color: #00ff9f;
    border-title-style: bold;
    padding: 0 1;
}
```

Panel titles appear **inside the border** (not as separate widgets) to save vertical space.

## Buttons

Keep button styling simple. Use default Textual button rendering.

- Label format: `(x) Action` where `x` is the hotkey
- Use `variant="error"` for destructive actions (Stop, Delete)

```python
Button("(s) Start", id="btn-start")
Button("(x) Stop", id="btn-stop", variant="error")
```

## Text Formatting

### Stat Labels
```python
f"[#666680]Label:[/]   [bold]{value}[/]"
f"[#666680]Label:[/]   [bold green]{good_value}[/]"
f"[#666680]Label:[/]   [yellow]{warning_value}[/]"
f"[#666680]Label:[/]   [red]{bad_value}[/]"
```

### Status Indicators
| Status | Format |
|--------|--------|
| Good/Online | `[bold green]ONLINE[/]` |
| Warning | `[yellow]WARN[/]` |
| Error/Offline | `[bold red]OFFLINE[/]` |

## Navigation

### Global Hotkeys (always available)
| Key | Action |
|-----|--------|
| `1-8` | Switch screens |
| `esc` | Go back |
| `q` | Quit |

These are defined in `LLMCScreen.BINDINGS` and inherited by all screens.

### Screen-Specific Hotkeys
Define additional hotkeys per screen using:
```python
BINDINGS = LLMCScreen.BINDINGS + [
    Binding("r", "refresh", "Refresh"),
    Binding("s", "start", "Start"),
]
```

## Screen Structure

All screens inherit from `LLMCScreen` and implement `compose_content()`:

```python
class MyScreen(LLMCScreen):
    SCREEN_TITLE = "MyScreen"  # For internal reference only
    
    BINDINGS = LLMCScreen.BINDINGS + [
        # Screen-specific bindings
    ]
    
    CSS = """
        /* Screen-specific CSS */
    """
    
    def compose_content(self) -> ComposeResult:
        # Yield your content here
        # Header and nav bar are handled by LLMCScreen
        pass
```

**Never override `compose()` directly** - use `compose_content()` instead.

## Log Panels

For live log streaming:

1. Use 500 line buffer: `self._max_log_lines = 500`
2. Only auto-scroll if user is at bottom
3. Track user scroll state to avoid fighting scroll

```python
def update_logs(self) -> None:
    # Only auto-scroll if user hasn't scrolled up
    scroll = self.query_one("#log-scroll", ScrollableContainer)
    if not self._user_scrolled:
        scroll.scroll_end(animate=False)

def on_scroll(self, event) -> None:
    scroll = self.query_one("#log-scroll", ScrollableContainer)
    at_bottom = scroll.scroll_y >= scroll.max_scroll_y - 1
    self._user_scrolled = not at_bottom
```

## Data Display

### DataTable
```css
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
```

### Tree Views
```css
Tree {
    background: #0a0a0f;
}
Tree > .tree--guides {
    color: #333344;
}
Tree > .tree--cursor {
    background: #2a2a4e;
}
```

## Spacing

- Panel padding: `padding: 0 1`
- Grid gutter: `grid-gutter: 1`
- Margins between elements: `margin: 0 1` or `margin: 1`

## Example Screen

```python
class ExampleScreen(LLMCScreen):
    SCREEN_TITLE = "Example"
    
    BINDINGS = LLMCScreen.BINDINGS + [
        Binding("r", "refresh", "Refresh"),
    ]
    
    CSS = """
    #main-grid {
        layout: grid;
        grid-size: 2;
        grid-gutter: 1;
        padding: 1;
        height: 1fr;
    }
    
    .panel {
        background: #1a1a2e;
        border: heavy #00b8ff;
        border-title-color: #00ff9f;
        border-title-style: bold;
        padding: 0 1;
    }
    """
    
    def compose_content(self) -> ComposeResult:
        with Grid(id="main-grid"):
            panel1 = Container(id="panel-1", classes="panel")
            panel1.border_title = "First Panel"
            with panel1:
                yield Static(id="content-1")
            
            panel2 = Container(id="panel-2", classes="panel")
            panel2.border_title = "Second Panel"
            with panel2:
                yield Static(id="content-2")
    
    def action_refresh(self):
        self.notify("Refreshed", severity="information")
```

---

**Author:** vmlinux + Claude  
**Date:** 2025-12-04  
**Status:** Active Standard
