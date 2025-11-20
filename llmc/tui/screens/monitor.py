#!/usr/bin/env python3
"""
Monitor Screen - Real-time system stats dashboard
"""
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal, Grid
from textual.screen import Screen
from textual.widgets import Static, Label
from textual.timer import Timer


class MonitorScreen(Screen):
    """Live monitoring dashboard showing system stats"""
    
    CSS = """
    MonitorScreen {
        layout: grid;
        grid-size: 2 3;
        grid-gutter: 1;
        padding: 1;
    }
    
    .stat-panel {
        height: 100%;
        border: heavy $primary;
        padding: 1 2;
    }
    
    .stat-title {
        text-style: bold;
        color: $accent;
    }
    
    .stat-value {
        text-align: center;
        text-style: bold;
        color: $success;
        margin-top: 1;
    }
    
    #log-panel {
        column-span: 2;
        border: heavy $secondary;
        padding: 1;
        height: 100%;
    }
    
    .log-line {
        color: $text-muted;
    }
    """
    
    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("escape", "app.pop_screen", "Back"),
    ]
    
    def __init__(self):
        super().__init__()
        self.logs = []
        self.start_time = datetime.now()
    
    def compose(self) -> ComposeResult:
        """Create the monitor layout"""
        with Container(classes="stat-panel"):
            yield Label("📂 Files Tracked", classes="stat-title")
            yield Static("0", id="files-tracked", classes="stat-value")
        
        with Container(classes="stat-panel"):
            yield Label("🧠 Graph Nodes", classes="stat-title")
            yield Static("0", id="graph-nodes", classes="stat-value")
        
        with Container(classes="stat-panel"):
            yield Label("🎫 Token Usage", classes="stat-title")
            yield Static("0", id="token-usage", classes="stat-value")
        
        with Container(classes="stat-panel"):
            yield Label("🔋 Daemon Status", classes="stat-title")
            yield Static("CHECKING...", id="daemon-status", classes="stat-value")
        
        with Vertical(id="log-panel"):
            yield Label("📝 Enrichment Log", classes="stat-title")
            yield Static("Initializing...\n", id="log-output", classes="log-line")
    
    def on_mount(self) -> None:
        """Start the update timer when mounted"""
        self.update_stats()
        self.set_interval(2.0, self.update_stats)
        self.set_interval(0.5, self.update_logs)
    
    def update_stats(self) -> None:
        """Fetch and display real stats"""
        try:
            repo_root = self.app.repo_root
            stats = self.get_repo_stats(repo_root)
            
            # Update stat widgets
            self.query_one("#files-tracked", Static).update(f"{stats['files_tracked']:,}")
            self.query_one("#graph-nodes", Static).update(f"{stats['graph_nodes']:,}")
            self.query_one("#token-usage", Static).update(f"{stats['token_usage']:,}")
            
            status_widget = self.query_one("#daemon-status", Static)
            if stats['daemon_status'] == "ONLINE":
                status_widget.update("[green]● ONLINE[/green]")
            else:
                status_widget.update("[red]● OFFLINE[/red]")
        
        except Exception as e:
            self.add_log(f"Error updating stats: {e}", "ERR")
    
    def update_logs(self) -> None:
        """Simulate log updates"""
        if random.random() < 0.3:
            files = ["auth.py", "user.py", "db.py", "graph.py", "utils.py"]
            f = random.choice(files)
            self.add_log(f"Enriching {f}...")
        
        if random.random() < 0.1:
            self.add_log("Graph sync complete.", "OK")
        
        # Update log display
        log_text = "\n".join(self.logs[-15:])  # Keep last 15 lines
        self.query_one("#log-output", Static).update(log_text)
    
    def add_log(self, msg: str, level: str = "INF") -> None:
        """Add a log entry"""
        ts = datetime.now().strftime("%H:%M:%S")
        color_map = {"OK": "green", "INF": "cyan", "ERR": "red"}
        color = color_map.get(level, "white")
        self.logs.append(f"[dim]{ts}[/dim] [{color}]{level}[/{color}] {msg}")
    
    def get_repo_stats(self, repo_root: Path) -> Dict[str, Any]:
        """Fetch real repo stats"""
        stats = {
            "files_tracked": 0,
            "graph_nodes": 0,
            "token_usage": 0,
            "daemon_status": "OFFLINE"
        }
        
        try:
            # Try to load real stats from RAG
            from tools.rag_nav.metadata import load_status
            from tools.rag_nav.tool_handlers import _load_graph
            
            # Check if index exists
            index_db = repo_root / ".rag" / "index_v2.db"
            if index_db.exists():
                stats["daemon_status"] = "ONLINE"
                
                # Get graph stats
                nodes, _ = _load_graph(repo_root)
                stats["graph_nodes"] = len(nodes)
                stats["files_tracked"] = len(set(n.get("path", "") for n in nodes if n.get("path")))
                
                # Estimate tokens (rough: 4 chars per token)
                total_content = sum(len(str(n.get("metadata", {}).get("summary", ""))) for n in nodes)
                stats["token_usage"] = total_content // 4
        
        except Exception as e:
            self.add_log(f"Stats error: {e}", "ERR")
        
        return stats
    
    def action_refresh(self) -> None:
        """Manually refresh stats"""
        self.update_stats()
        self.add_log("Stats refreshed", "OK")
