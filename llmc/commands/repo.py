"""
Repository management commands for LLMC.

Commands:
    llmc repo add <path>    - Full bootstrap: init + index + register
    llmc repo rm <path>     - Unregister from daemon
    llmc repo clean <path>  - Nuclear: delete all LLMC artifacts
    llmc repo list          - Show status of all registered repos
"""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime, timezone

import typer
from rich.console import Console
from rich.table import Table

from llmc.core import find_repo_root

app = typer.Typer(no_args_is_help=True)
console = Console()

# State file location - must match tools/rag/service.py
STATE_FILE = Path.home() / ".llmc" / "rag-service.json"


def _get_state() -> dict:
    """Load service state."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"repos": [], "pid": None, "status": "stopped", "last_cycle": None, "interval": 180}


def _save_state(state: dict) -> None:
    """Save service state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _get_repo_stats(repo_path: Path) -> dict:
    """Get stats for a repository."""
    stats = {
        "path": str(repo_path),
        "name": repo_path.name,
        "exists": repo_path.exists(),
        "has_llmc": False,
        "has_config": False,
        "has_db": False,
        "spans": 0,
        "enriched": 0,
        "embedded": 0,
    }
    
    if not repo_path.exists():
        return stats
    
    # Check for LLMC artifacts
    llmc_dir = repo_path / ".llmc"
    config_file = repo_path / "llmc.toml"
    
    stats["has_llmc"] = llmc_dir.exists()
    stats["has_config"] = config_file.exists()
    
    # Find database - check .rag/ first (RAG indexer default), then .llmc/
    rag_dir = repo_path / ".rag"
    db_path = rag_dir / "index_v2.db"
    if not db_path.exists():
        db_path = llmc_dir / "index_v2.db"
    if not db_path.exists():
        db_path = llmc_dir / "rag.db"
    
    if db_path.exists():
        stats["has_db"] = True
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Get span count
            try:
                cursor.execute("SELECT COUNT(*) FROM spans")
                stats["spans"] = cursor.fetchone()[0]
            except Exception:
                pass
            
            # Get enrichment count
            try:
                cursor.execute("SELECT COUNT(*) FROM enrichments")
                stats["enriched"] = cursor.fetchone()[0]
            except Exception:
                pass
            
            # Get embedding count
            try:
                cursor.execute("SELECT COUNT(*) FROM embeddings")
                stats["embedded"] = cursor.fetchone()[0]
            except Exception:
                pass
            
            conn.close()
        except Exception:
            pass
    
    return stats


@app.command("add")
def add(
    path: str = typer.Argument(..., help="Path to repository to add"),
    skip_index: bool = typer.Option(False, "--no-index", help="Skip initial indexing"),
    skip_enrich: bool = typer.Option(False, "--no-enrich", help="Skip initial enrichment"),
):
    """
    Add and bootstrap a repository for LLMC.
    
    This does everything needed to get a repo working:
    1. Creates .llmc/ directory and llmc.toml config
    2. Initializes the database
    3. Indexes all source files
    4. Registers with the daemon for ongoing enrichment
    """
    repo_path = Path(path).resolve()
    
    if not repo_path.exists():
        console.print(f"[red]❌ Path does not exist: {path}[/red]")
        raise typer.Exit(code=1)
    
    if not repo_path.is_dir():
        console.print(f"[red]❌ Path is not a directory: {path}[/red]")
        raise typer.Exit(code=1)
    
    console.print(f"[bold]🚀 Bootstrapping LLMC for: {repo_path.name}[/bold]")
    
    # Step 1: Create .llmc/ directory
    llmc_dir = repo_path / ".llmc"
    llmc_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"  ✅ Created .llmc/ directory")
    
    # Create logs subdirectory
    (llmc_dir / "logs").mkdir(exist_ok=True)
    
    # Step 2: Create llmc.toml if it doesn't exist
    config_path = repo_path / "llmc.toml"
    if not config_path.exists():
        default_config = {
            "storage": {"index_path": ".rag/index_v2.db"},  # Must match RAG indexer default
            "logging": {
                "log_directory": ".llmc/logs",
                "enable_rotation": True,
                "max_file_size_mb": 10,
            },
            "indexing": {
                "exclude_dirs": [
                    ".git", ".llmc", ".venv", "__pycache__",
                    "node_modules", "dist", "build", ".pytest_cache",
                ]
            },
            "embeddings": {
                "default_profile": "docs",
                "profiles": {
                    "docs": {"provider": "ollama", "model": "nomic-embed-text", "dimension": 768}
                },
            },
            "rag": {"enabled": True},
        }
        import tomli_w
        with open(config_path, "wb") as f:
            tomli_w.dump(default_config, f)
        console.print(f"  ✅ Created llmc.toml configuration")
    else:
        console.print(f"  ℹ️  llmc.toml already exists")
    
    # Step 3: Initialize database
    db_path = llmc_dir / "index_v2.db"
    try:
        from tools.rag.database import Database
        db = Database(db_path)
        db.close()
        console.print(f"  ✅ Initialized database")
    except Exception as e:
        console.print(f"  [yellow]⚠️  Database init failed: {e}[/yellow]")
    
    # Step 4: Run indexing
    if not skip_index:
        console.print(f"  📂 Indexing files...")
        try:
            import os as _os
            from tools.rag.indexer import index_repo
            
            # Save CWD and change to target repo
            orig_cwd = Path.cwd()
            _os.chdir(repo_path)
            
            try:
                result = index_repo()
                console.print(f"  ✅ Indexed {result.files} files, {result.spans} spans")
            finally:
                _os.chdir(orig_cwd)
        except Exception as e:
            console.print(f"  [yellow]⚠️  Indexing failed: {e}[/yellow]")
    else:
        console.print(f"  ⏭️  Skipped indexing (--no-index)")
    
    # Step 5: Register with daemon
    state = _get_state()
    repo_str = str(repo_path)
    if repo_str not in state["repos"]:
        state["repos"].append(repo_str)
        _save_state(state)
        console.print(f"  ✅ Registered with daemon")
    else:
        console.print(f"  ℹ️  Already registered with daemon")
    
    # Show summary
    stats = _get_repo_stats(repo_path)
    console.print(f"\n[bold green]✨ {repo_path.name} is ready![/bold green]")
    console.print(f"   Spans indexed: {stats['spans']}")
    console.print(f"   Enriched: {stats['enriched']}")
    
    if not skip_enrich and stats['spans'] > 0:
        console.print(f"\n💡 Start enrichment with: llmc service start")


@app.command("rm")
def rm(
    path: str = typer.Argument(..., help="Path to repository to unregister"),
):
    """
    Unregister a repository from the daemon.
    
    This removes the repo from daemon tracking but keeps all .llmc/ artifacts.
    Use 'llmc repo clean' to completely remove LLMC from a repo.
    """
    repo_path = Path(path).resolve()
    state = _get_state()
    repo_str = str(repo_path)
    
    if repo_str in state["repos"]:
        state["repos"].remove(repo_str)
        _save_state(state)
        console.print(f"[green]✅ Unregistered: {repo_path}[/green]")
        console.print(f"   .llmc/ artifacts remain - use 'llmc repo clean' to remove")
    else:
        console.print(f"[yellow]ℹ️  Not registered: {repo_path}[/yellow]")


@app.command("clean")
def clean(
    path: str = typer.Argument(..., help="Path to repository to clean"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """
    Completely remove LLMC from a repository.
    
    This deletes:
    - .llmc/ directory (database, logs, cache)
    - llmc.toml configuration
    - Removes from daemon tracking
    """
    repo_path = Path(path).resolve()
    
    if not repo_path.exists():
        console.print(f"[red]❌ Path does not exist: {path}[/red]")
        raise typer.Exit(code=1)
    
    llmc_dir = repo_path / ".llmc"
    config_file = repo_path / "llmc.toml"
    
    if not llmc_dir.exists() and not config_file.exists():
        console.print(f"[yellow]ℹ️  No LLMC artifacts found in: {repo_path}[/yellow]")
        return
    
    # Confirm
    if not force:
        console.print(f"[bold red]⚠️  This will permanently delete:[/bold red]")
        if llmc_dir.exists():
            console.print(f"   - {llmc_dir}")
        if config_file.exists():
            console.print(f"   - {config_file}")
        
        confirm = typer.confirm("Are you sure?")
        if not confirm:
            console.print("Cancelled.")
            raise typer.Exit(code=0)
    
    # Unregister first
    state = _get_state()
    repo_str = str(repo_path)
    if repo_str in state["repos"]:
        state["repos"].remove(repo_str)
        _save_state(state)
        console.print(f"  ✅ Unregistered from daemon")
    
    # Delete artifacts
    if llmc_dir.exists():
        shutil.rmtree(llmc_dir)
        console.print(f"  ✅ Deleted .llmc/")
    
    if config_file.exists():
        config_file.unlink()
        console.print(f"  ✅ Deleted llmc.toml")
    
    console.print(f"\n[green]✨ LLMC removed from {repo_path.name}[/green]")


@app.command("list")
def list_repos():
    """
    Show status of all registered repositories.
    """
    state = _get_state()
    
    if not state["repos"]:
        console.print("[yellow]No repositories registered.[/yellow]")
        console.print("\nAdd a repo: llmc repo add <path>")
        return
    
    # Header
    console.print("[bold]LLMC Repository Status[/bold]")
    console.print("=" * 60)
    
    # Service status
    pid = state.get("pid")
    if pid:
        try:
            os.kill(pid, 0)
            console.print(f"Daemon: [green]🟢 running[/green] (PID {pid})")
        except OSError:
            console.print(f"Daemon: [red]🔴 stopped[/red] (stale PID {pid})")
    else:
        console.print(f"Daemon: [red]🔴 stopped[/red]")
    
    # Last cycle
    last_cycle = state.get("last_cycle")
    if last_cycle:
        try:
            last = datetime.fromisoformat(last_cycle)
            ago = (datetime.now(timezone.utc) - last).total_seconds()
            console.print(f"Last cycle: {int(ago)}s ago")
        except Exception:
            pass
    
    console.print()
    
    # Repository table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Repository", style="cyan")
    table.add_column("Spans", justify="right")
    table.add_column("Enriched", justify="right")
    table.add_column("Embedded", justify="right")
    table.add_column("Status")
    
    for repo_str in state["repos"]:
        repo_path = Path(repo_str)
        stats = _get_repo_stats(repo_path)
        
        # Determine status
        if not stats["exists"]:
            status = "[red]❌ missing[/red]"
        elif not stats["has_llmc"]:
            status = "[yellow]⚠️ not init[/yellow]"
        elif not stats["has_db"]:
            status = "[yellow]⚠️ no db[/yellow]"
        elif stats["enriched"] == 0:
            status = "[blue]📂 indexed[/blue]"
        else:
            pct = (stats["enriched"] / stats["spans"] * 100) if stats["spans"] > 0 else 0
            if pct >= 90:
                status = "[green]✅ enriched[/green]"
            else:
                status = f"[yellow]🔄 {pct:.0f}%[/yellow]"
        
        table.add_row(
            stats["name"],
            str(stats["spans"]),
            str(stats["enriched"]),
            str(stats["embedded"]),
            status,
        )
    
    console.print(table)
    console.print(f"\nTotal: {len(state['repos'])} repos")
