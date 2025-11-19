#!/usr/bin/env python3
"""
LLMC: The Cyberpunk Console - 6 Panel Layout Demo
"""
import time
import random
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Conditional imports so it doesn't crash if you haven't pip installed yet
try:
    import typer
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.live import Live
    from rich.table import Table
    from rich.text import Text
    from rich.align import Align
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
except ImportError:
    print("Please install 'typer' and 'rich' to enable the CLI.")
    print("pip install typer rich")
    exit(1)

# Import LLMC core modules
try:
    from tools.rag_nav.metadata import load_status
    from tools.rag_nav.tool_handlers import _load_graph, _rag_graph_path # _load_graph is private, but okay for demo
except ImportError:
    console.print("[bold red]ERROR:[/bold red] LLMC core modules not found. Ensure PYTHONPATH is set or you are in the correct directory.", style="bold red")
    console.print("         Run 'export PYTHONPATH=$(pwd)' from the project root.", style="bold red")
    exit(1)


app = typer.Typer()
console = Console()

LLMC_ROOT = Path(__file__).parent.parent.parent # Assumes llmc/cli.py is in llmc/llmc/cli.py

def make_layout() -> Layout:
    """Define the 6-panel grid."""
    layout = Layout(name="root")

    layout.split(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3)
    )

    layout["body"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=2) # Give more space to logs/status
    )

    layout["left"].split_column(
        Layout(name="menu", ratio=2),
        Layout(name="help", ratio=1)
    )

    layout["right"].split_column(
        Layout(name="context", ratio=1),
        Layout(name="log", ratio=2)
    )

    return layout


def get_repo_stats(repo_root: Path) -> Dict[str, Any]:
    """Fetch real-time stats from the repo's RAG data."""
    stats = {
        "files_tracked": 0,
        "graph_nodes": 0,
        "enriched_nodes": 0,
        "token_usage": 0,
        "freshness_state": "UNKNOWN",
        "daemon_status": "OFFLINE",
        "last_indexed_at": "Never",
        "error": None
    }

    try:
        # Get index status
        index_status = load_status(repo_root)
        if index_status:
            stats["freshness_state"] = index_status.freshness_state
            stats["last_indexed_at"] = index_status.last_indexed_at if index_status.last_indexed_at else "Never"

        # Get graph stats
        nodes, _ = _load_graph(repo_root)
        stats["graph_nodes"] = len(nodes)
        stats["enriched_nodes"] = sum(1 for n in nodes if n.get("metadata", {}).get("summary"))
        
        # Approximate token usage (simple heuristic: 4 chars/token avg)
        # This is a placeholder; real token count would be in the DB.
        total_content_len = sum(len(n.get("metadata", {}).get("summary", "")) for n in nodes)
        stats["token_usage"] = total_content_len // 4 # Rough estimate

        # Daemon status (placeholder for now, real implementation would read PID file or socket)
        # For demo, assume ON if graph exists.
        if Path(repo_root / ".llmc" / "rag" / "index_v2.db").exists():
             stats["daemon_status"] = "ONLINE"
        else:
            stats["daemon_status"] = "OFFLINE"
        
        # Files tracked (can be from the graph if it stored file entities, or count .py files)
        # For simplicity, let's use graph_nodes as a proxy for now.
        stats["files_tracked"] = len(nodes) # Will improve this later

    except Exception as e:
        stats["error"] = str(e)
        stats["freshness_state"] = "ERROR"
        stats["daemon_status"] = "ERROR" # Indicate daemon related issues

    return stats


class DashboardState:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.logs: List[str] = []
        self.menu_idx = 0
        self.menu_items = ["Monitor System", "Search Code", "Configuration", "System Doctor", "Agent Status"]
        self.start_time = datetime.now()
        self.last_stats_update = datetime.min # Force immediate update
        self.current_stats: Dict[str, Any] = {}

    def add_log(self, msg: str, level: str = "INF"):
        ts = datetime.now().strftime("%H:%M:%S")
        color = "green" if level == "OK " else "cyan" if level == "INF" else "red"
        self.logs.append(f"[dim]{ts}[/dim] [{color}]{level}[/{color}] {msg}")
        if len(self.logs) > 15: # Keep last 15 entries
            self.logs.pop(0)

    def update(self):
        # Update real stats every few seconds or if error
        if (datetime.now() - self.last_stats_update).total_seconds() > 2 or self.current_stats.get("error"):
            self.current_stats = get_repo_stats(self.repo_root)
            if self.current_stats.get("error"):
                self.add_log(f"Error fetching stats: {self.current_stats['error']}", "ERR")
            else:
                self.add_log("Stats refreshed.", "OK ")
            self.last_stats_update = datetime.now()
            
        # Simulate log entries
        if random.random() < 0.1:
            files = ["auth.py", "user.py", "db.py", "graph.py", "utils.py"]
            f = random.choice(files)
            self.add_log(f"Enriching [bold]{f}[/bold]...", "INF")
            
        if random.random() < 0.05:
            self.add_log("Graph sync complete.", "OK ")


def make_layout() -> Layout:
    """Define the 6-panel grid."""
    layout = Layout(name="root")

    layout.split(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="footer", size=3)
    )

    layout["body"].split_row(
        Layout(name="left", ratio=1),
        Layout(name="right", ratio=2) # Give more space to logs/status
    )

    layout["left"].split_column(
        Layout(name="menu", ratio=2),
        Layout(name="help", ratio=1)
    )

    layout["right"].split_column(
        Layout(name="context", ratio=1),
        Layout(name="log", ratio=2)
    )

    return layout


@app.command()
def search(query: str):
    """Search the codebase (Demo)."""
    console.print(f"Searching for {query}...")

@app.command()
def monitor():
    """Launch the 6-Panel Dashboard."""
    repo_root = Path("./").resolve() # Assume CWD is repo root for now
    layout = make_layout()
    state = DashboardState(repo_root)

    # Header
    layout["header"].update(
        Panel(
            Text(f"LLMC v0.5.0 [DEV] --repo {repo_root}", justify="center", style="bold white"),
            style="white on blue"
        )
    )

    # Footer
    layout["footer"].update(
        Panel(
            Text("[q] Quit  [s] Save & Exit  [h] Help", justify="center", style="dim white"),
            style="on black"
        )
    )

    with Live(layout, refresh_per_second=4, screen=True):
        while True:
            state.update()
            stats = state.current_stats

            # 1. Sub Menu (Top Left)
            menu_text = Text()
            for i, item in enumerate(state.menu_items):
                if i == state.menu_idx:
                    menu_text.append(f"> [{i+1}] {item}\n", style="bold yellow reverse")
                else:
                    menu_text.append(f"  [{i+1}] {item}\n", style="white")
            
            layout["menu"].update(
                Panel(menu_text, title="[bold]Navigation[/bold]", border_style="yellow")
            )

            # 2. Help/Info (Bottom Left)
            help_content = ""
            if state.menu_idx == 0:
                help_content = "View live system metrics,\nactive agents, and\nresource usage."
            elif state.menu_idx == 1:
                help_content = "Search the codebase using\nRAG + Fuzzy Linking.\nSupports regex."
            elif state.menu_idx == 2:
                help_content = "Edit llmc.toml settings\nand configure LLM\nproviders."
            else:
                help_content = "Select an option to\nsee details."

            layout["help"].update(
                Panel(Text(help_content, style="dim cyan"), title="[bold]Context[/bold]", border_style="cyan")
            )

            # 3. Context/Status (Top Right)
            # Using a Grid/Table for alignment
            grid = Table.grid(expand=True)
            grid.add_column(justify="left")
            grid.add_column(justify="right")
            
            grid.add_row("📂 Files Tracked:", f"[bold]{stats['files_tracked']}[/bold]")
            grid.add_row("🧠 Graph Nodes:", f"[bold]{stats['graph_nodes']}[/bold]")
            grid.add_row("🧠 Enriched Nodes:", f"[bold]{stats['enriched_nodes']}[/bold]")
            grid.add_row("🎫 Token Usage:", f"[bold yellow]{stats['token_usage']:,}[/bold yellow]")
            grid.add_row("🔋 Daemon Status:", f"[bold green]{stats['daemon_status']}[/bold green]")
            grid.add_row("📈 Freshness:", f"[bold {('red' if stats['freshness_state'] == 'STALE' else 'green')}]"
                                           f"{stats['freshness_state']}[/bold]")
            grid.add_row("⏱️  Uptime:", str(datetime.now() - state.start_time).split('.')[0])
            grid.add_row("📝 Last Indexed:", stats['last_indexed_at'].split('T')[0] if stats['last_indexed_at'] and 'T' in stats['last_indexed_at'] else "Never")


            layout["context"].update(
                Panel(grid, title="[bold]System Status[/bold]", border_style="blue")
            )

            # 4. Enrichment Log (Bottom Right - Always On)
            log_render = "\n".join(state.logs)
            layout["log"].update(
                Panel(Text.from_markup(log_render), title="[bold]Enrichment Log[/bold]", border_style="green")
            )

            time.sleep(0.1)

if __name__ == "__main__":
    app()