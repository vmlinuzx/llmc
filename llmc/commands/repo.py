"""
Repository management commands for LLMC.

Commands:
    llmc repo init              - Quick init: create .llmc/ workspace only
    llmc repo register <path>   - Register repo with LLMC: init + index + daemon tracking
    llmc repo bootstrap <path>  - Re-bootstrap: fix configs without re-registering
    llmc repo rm <path>         - Unregister from daemon
    llmc repo clean <path>      - Nuclear: delete all LLMC artifacts
    llmc repo list              - Show status of all registered repos
    llmc repo validate <path>   - Validate repo config
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

app = typer.Typer(
    help="Repository management: register, bootstrap, validate, and manage LLMC repos.",
    no_args_is_help=True,
)
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
        "files": 0,
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
            
            # Get file count
            try:
                cursor.execute("SELECT COUNT(*) FROM files")
                stats["files"] = cursor.fetchone()[0]
            except Exception:
                pass
            
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


@app.command("init")
def init(
    path: str = typer.Argument(".", help="Path to initialize (default: current directory)"),
):
    """
    Quick init: create .llmc/ workspace and llmc.toml only.
    
    This is the lightest-weight setup - just creates the workspace structure
    without indexing files or registering with the daemon.
    
    For full setup, use: llmc repo register <path>
    
    Examples:
        llmc repo init           # Init current directory
        llmc repo init /path     # Init specific path
    """
    import tomli_w
    from tools.rag.database import Database
    
    repo_path = Path(path).resolve()
    
    if not repo_path.exists():
        console.print(f"[red]❌ Path does not exist: {path}[/red]")
        raise typer.Exit(code=1)
    
    if not repo_path.is_dir():
        console.print(f"[red]❌ Path is not a directory: {path}[/red]")
        raise typer.Exit(code=1)
    
    console.print(f"[bold]📁 Initializing LLMC workspace in: {repo_path.name}[/bold]")
    
    # 1. Create .llmc/ directory
    llmc_dir = repo_path / ".llmc"
    llmc_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"  ✅ Created .llmc/ directory")
    
    # 2. Create logs subdirectory
    (llmc_dir / "logs").mkdir(exist_ok=True)
    
    # 3. Create llmc.toml if missing
    config_path = repo_path / "llmc.toml"
    if not config_path.exists():
        default_config = {
            "storage": {"index_path": ".rag/index_v2.db"},
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
                    "docs": {
                        "provider": "ollama",
                        "model": "nomic-embed-text",
                        "dimension": 768,
                    }
                },
            },
            "rag": {"enabled": True},
        }
        with open(config_path, "wb") as f:
            tomli_w.dump(default_config, f)
        console.print(f"  ✅ Created llmc.toml configuration")
    else:
        console.print(f"  ℹ️  llmc.toml already exists")
    
    # 4. Initialize database
    rag_dir = repo_path / ".rag"
    rag_dir.mkdir(parents=True, exist_ok=True)
    db_path = rag_dir / "index_v2.db"
    try:
        db = Database(db_path)
        db.close()
        console.print(f"  ✅ Initialized database")
    except Exception as e:
        console.print(f"  [yellow]⚠️  Database init failed: {e}[/yellow]")
    
    console.print(f"\n[bold green]✨ Workspace initialized![/bold green]")
    console.print(f"\nNext steps:")
    console.print(f"  • Full setup with indexing: [cyan]llmc repo register {path}[/cyan]")
    console.print(f"  • Start daemon:            [cyan]llmc service start[/cyan]")


@app.command("register")
def register(
    path: str = typer.Argument(..., help="Path to repository to register"),
    skip_index: bool = typer.Option(False, "--no-index", help="Skip initial indexing"),
    skip_enrich: bool = typer.Option(False, "--no-enrich", help="Skip initial enrichment"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Run interactive configuration wizard"),
):
    """
    Register a repository with LLMC.
    
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

    if interactive:
        from llmc.commands.wizard import run_wizard
        run_wizard(repo_path)
    
    console.print(f"[bold]🚀 Registering {repo_path.name} with LLMC[/bold]")
    
    # Step 1: Create .llmc/ directory
    llmc_dir = repo_path / ".llmc"
    llmc_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"  ✅ Created .llmc/ directory")
    
    # Create logs subdirectory
    (llmc_dir / "logs").mkdir(exist_ok=True)
    
    # Step 1a: Copy LLMCAGENTS.md for AI agent integration
    # Look for canonical file in llmc install location
    agents_source = None
    candidates = [
        Path(__file__).parent.parent.parent / "LLMCAGENTS.md",  # Relative to this file
        Path.home() / ".llmc" / "LLMCAGENTS.md",  # Global install
    ]
    for candidate in candidates:
        if candidate.exists():
            agents_source = candidate
            break
    
    agents_dest = llmc_dir / "LLMCAGENTS.md"
    if agents_source and not agents_dest.exists():
        try:
            shutil.copy(agents_source, agents_dest)
            console.print(f"  ✅ Installed LLMCAGENTS.md (for AI agent integration)")
        except Exception as e:
            console.print(f"  [yellow]⚠️  Could not copy LLMCAGENTS.md: {e}[/yellow]")
    elif agents_dest.exists():
        console.print(f"  ℹ️  LLMCAGENTS.md already exists")
    
    # Step 1b: Update .gitignore
    gitignore_path = repo_path / ".gitignore"
    gitignore_entries = [".llmc/", ".rag/"]
    try:
        existing = gitignore_path.read_text() if gitignore_path.exists() else ""
        missing = [e for e in gitignore_entries if e not in existing]
        if missing:
            with open(gitignore_path, "a") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                f.write("# LLMC artifacts\n")
                for entry in missing:
                    f.write(f"{entry}\n")
            console.print(f"  ✅ Added {', '.join(missing)} to .gitignore")
        else:
            console.print(f"  ℹ️  .gitignore already has LLMC entries")
    except Exception as e:
        console.print(f"  [yellow]⚠️  Could not update .gitignore: {e}[/yellow]")
    
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
            # ENRICHMENT CONFIG - Required for LLM-based code summarization
            "enrichment": {
                "default_chain": "code_enrichment_models",
                "batch_size": 50,
                "est_tokens_per_span": 350,
                "enforce_latin1_enrichment": True,
                "max_failures_per_span": 4,
                "enable_routing": True,
                "routes": {
                    "docs": "code_enrichment_models",
                    "code": "code_enrichment_models",
                },
                "chain": [
                    {
                        "name": "qwen3-4b-instruct",
                        "chain": "code_enrichment_models",
                        "provider": "ollama",
                        "model": "qwen3:4b-instruct",
                        "url": "http://localhost:11434",
                        "routing_tier": "4b",
                        "timeout_seconds": 90,
                        "enabled": True,
                        "options": {"num_ctx": 8192, "temperature": 0.2},
                    },
                    {
                        "name": "qwen2.5-7b-instruct",
                        "chain": "code_enrichment_models",
                        "provider": "ollama",
                        "model": "qwen2.5:7b-instruct",
                        "url": "http://localhost:11434",
                        "routing_tier": "7b",
                        "timeout_seconds": 120,
                        "enabled": True,
                        "options": {"num_ctx": 8192, "temperature": 0.2},
                    },
                ],
            },
            "embeddings": {
                "default_profile": "docs",
                "profiles": {
                    "docs": {
                        "provider": "ollama",
                        "model": "nomic-embed-text",
                        "dimension": 768,
                        "ollama": {
                            "api_base": "http://localhost:11434",
                            "timeout": 120,
                        },
                    }
                },
                "routes": {
                    "docs": {"profile": "docs", "index": "embeddings"},
                    "code": {"profile": "docs", "index": "embeddings"},
                },
            },
            "routing": {
                "slice_type_to_route": {
                    "code": "code",
                    "docs": "docs",
                    "config": "docs",
                    "data": "docs",
                    "other": "docs",
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


@app.command("bootstrap")
def bootstrap(
    path: str = typer.Argument(..., help="Path to repository to bootstrap"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
    skip_index: bool = typer.Option(False, "--no-index", help="Skip re-indexing"),
):
    """
    Re-bootstrap an existing repository.
    
    Use this to fix broken configs or regenerate LLMC workspace files.
    Unlike 'register', this does NOT add the repo to daemon tracking.
    
    Steps performed:
    1. Recreates .llmc/ directory structure
    2. Regenerates llmc.toml (if --force or missing)
    3. Reinitializes the database
    4. Re-indexes files (unless --no-index)
    
    Examples:
        llmc repo bootstrap .              # Fix current repo
        llmc repo bootstrap . --force      # Force regenerate config
        llmc repo bootstrap /path/to/repo  # Fix another repo
    """
    repo_path = Path(path).resolve()
    
    if not repo_path.exists():
        console.print(f"[red]❌ Path does not exist: {path}[/red]")
        raise typer.Exit(code=1)
    
    if not repo_path.is_dir():
        console.print(f"[red]❌ Path is not a directory: {path}[/red]")
        raise typer.Exit(code=1)
    
    console.print(f"[bold]🔧 Re-bootstrapping {repo_path.name}[/bold]")
    
    # Step 1: Ensure .llmc/ directory exists
    llmc_dir = repo_path / ".llmc"
    llmc_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"  ✅ Ensured .llmc/ directory")
    
    # Create logs subdirectory
    (llmc_dir / "logs").mkdir(exist_ok=True)
    
    # Step 2: Copy LLMCAGENTS.md
    agents_source = None
    candidates = [
        Path(__file__).parent.parent.parent / "LLMCAGENTS.md",
        Path.home() / ".llmc" / "LLMCAGENTS.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            agents_source = candidate
            break
    
    agents_dest = llmc_dir / "LLMCAGENTS.md"
    if agents_source and (force or not agents_dest.exists()):
        try:
            shutil.copy(agents_source, agents_dest)
            console.print(f"  ✅ {'Replaced' if force else 'Installed'} LLMCAGENTS.md")
        except Exception as e:
            console.print(f"  [yellow]⚠️  Could not copy LLMCAGENTS.md: {e}[/yellow]")
    elif agents_dest.exists():
        console.print(f"  ℹ️  LLMCAGENTS.md already exists (use --force to replace)")
    
    # Step 3: Update .gitignore
    gitignore_path = repo_path / ".gitignore"
    gitignore_entries = [".llmc/", ".rag/"]
    try:
        existing = gitignore_path.read_text() if gitignore_path.exists() else ""
        missing = [e for e in gitignore_entries if e not in existing]
        if missing:
            with open(gitignore_path, "a") as f:
                if existing and not existing.endswith("\n"):
                    f.write("\n")
                f.write("# LLMC artifacts\n")
                for entry in missing:
                    f.write(f"{entry}\n")
            console.print(f"  ✅ Added {', '.join(missing)} to .gitignore")
        else:
            console.print(f"  ℹ️  .gitignore already has LLMC entries")
    except Exception as e:
        console.print(f"  [yellow]⚠️  Could not update .gitignore: {e}[/yellow]")
    
    # Step 4: Create/replace llmc.toml
    config_path = repo_path / "llmc.toml"
    if force or not config_path.exists():
        default_config = {
            "storage": {"index_path": ".rag/index_v2.db"},
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
            "enrichment": {
                "default_chain": "code_enrichment_models",
                "batch_size": 50,
                "est_tokens_per_span": 350,
                "enforce_latin1_enrichment": True,
                "max_failures_per_span": 4,
                "enable_routing": True,
                "routes": {
                    "docs": "code_enrichment_models",
                    "code": "code_enrichment_models",
                },
                "chain": [
                    {
                        "name": "qwen3-4b",
                        "chain": "code_enrichment_models",
                        "provider": "ollama",
                        "model": "qwen3:4b-instruct",
                        "url": "http://localhost:11434",
                        "routing_tier": "4b",
                        "timeout_seconds": 90,
                        "enabled": True,
                        "options": {"num_ctx": 8192, "temperature": 0.2},
                    },
                    {
                        "name": "qwen3-8b",
                        "chain": "code_enrichment_models",
                        "provider": "ollama",
                        "model": "qwen3:8b",
                        "url": "http://localhost:11434",
                        "routing_tier": "8b",
                        "timeout_seconds": 120,
                        "enabled": True,
                        "options": {"num_ctx": 8192, "temperature": 0.2},
                    },
                    {
                        "name": "qwen2.5-14b",
                        "chain": "code_enrichment_models",
                        "provider": "ollama",
                        "model": "qwen2.5:14b-instruct-q4_K_M",
                        "url": "http://localhost:11434",
                        "routing_tier": "14b",
                        "timeout_seconds": 180,
                        "enabled": True,
                        "options": {"num_ctx": 12288, "temperature": 0.2},
                    },
                ],
            },
            "embeddings": {
                "default_profile": "docs",
                "profiles": {
                    "docs": {
                        "provider": "ollama",
                        "model": "hf.co/second-state/jina-embeddings-v2-base-code-GGUF:Q5_K_M",
                        "dimension": 768,
                        "ollama": {
                            "api_base": "http://localhost:11434",
                            "timeout": 120,
                        },
                    }
                },
                "routes": {
                    "docs": {"profile": "docs", "index": "embeddings"},
                    "code": {"profile": "docs", "index": "embeddings"},
                },
            },
            "routing": {
                "slice_type_to_route": {
                    "code": "code",
                    "docs": "docs",
                    "config": "docs",
                    "data": "docs",
                    "other": "docs",
                },
            },
            "rag": {"enabled": True},
        }
        import tomli_w
        with open(config_path, "wb") as f:
            tomli_w.dump(default_config, f)
        console.print(f"  ✅ {'Replaced' if force and config_path.exists() else 'Created'} llmc.toml")
    else:
        console.print(f"  ℹ️  llmc.toml already exists (use --force to replace)")
    
    # Step 5: Initialize/reinit database
    rag_dir = repo_path / ".rag"
    rag_dir.mkdir(parents=True, exist_ok=True)
    db_path = rag_dir / "index_v2.db"
    try:
        from tools.rag.database import Database
        db = Database(db_path)
        db.close()
        console.print(f"  ✅ Initialized database")
    except Exception as e:
        console.print(f"  [yellow]⚠️  Database init failed: {e}[/yellow]")
    
    # Step 6: Re-index if requested
    if not skip_index:
        console.print(f"  📂 Re-indexing files...")
        try:
            import os as _os
            from tools.rag.indexer import index_repo
            
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
    
    # Show summary
    stats = _get_repo_stats(repo_path)
    console.print(f"\n[bold green]🔧 {repo_path.name} re-bootstrapped![/bold green]")
    console.print(f"   Spans: {stats['spans']}")
    console.print(f"   Enriched: {stats['enriched']}")
    
    # Check if registered
    state = _get_state()
    if str(repo_path) not in state["repos"]:
        console.print(f"\n[yellow]💡 Repo not registered with daemon. Run: llmc repo register {path}[/yellow]")


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
    - .llmc/ directory (logs, cache)
    - .rag/ directory (database, embeddings, graph)
    - llmc.toml configuration
    - Removes from daemon tracking
    """
    repo_path = Path(path).resolve()
    
    if not repo_path.exists():
        console.print(f"[red]❌ Path does not exist: {path}[/red]")
        raise typer.Exit(code=1)
    
    llmc_dir = repo_path / ".llmc"
    rag_dir = repo_path / ".rag"
    config_file = repo_path / "llmc.toml"
    
    if not llmc_dir.exists() and not rag_dir.exists() and not config_file.exists():
        console.print(f"[yellow]ℹ️  No LLMC artifacts found in: {repo_path}[/yellow]")
        return
    
    # Confirm
    if not force:
        console.print(f"[bold red]⚠️  This will permanently delete:[/bold red]")
        if llmc_dir.exists():
            console.print(f"   - {llmc_dir}")
        if rag_dir.exists():
            console.print(f"   - {rag_dir}")
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
    
    if rag_dir.exists():
        shutil.rmtree(rag_dir)
        console.print(f"  ✅ Deleted .rag/ (database)")
    
    if config_file.exists():
        config_file.unlink()
        console.print(f"  ✅ Deleted llmc.toml")
    
    console.print(f"\n[green]✨ LLMC removed from {repo_path.name}[/green]")


@app.command("nukerag")
def nukerag(
    path: str = typer.Argument(".", help="Path to repository"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """
    Clear all enrichment data for a repository.
    
    This deletes enrichments and embeddings but keeps:
    - File index (no need to re-scan files)
    - Configuration (llmc.toml)
    - Daemon registration
    
    Use this when enrichments are corrupted or you want to
    re-run enrichment with different models/prompts.
    """
    repo_path = Path(path).resolve()
    
    if not repo_path.exists():
        console.print(f"[red]❌ Path does not exist: {path}[/red]")
        raise typer.Exit(code=1)
    
    rag_dir = repo_path / ".rag"
    db_path = rag_dir / "index_v2.db"
    
    if not db_path.exists():
        console.print(f"[yellow]ℹ️  No RAG database found in: {repo_path}[/yellow]")
        return
    
    # Count enrichments
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM enrichments")
        enrichment_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        embedding_count = cursor.fetchone()[0]
        conn.close()
    except Exception as e:
        console.print(f"[red]❌ Failed to read database: {e}[/red]")
        raise typer.Exit(code=1)
    
    if enrichment_count == 0 and embedding_count == 0:
        console.print(f"[yellow]ℹ️  No enrichment data to clear[/yellow]")
        return
    
    # Confirm
    if not force:
        console.print(f"[bold red]⚠️  This will permanently delete:[/bold red]")
        console.print(f"   - {enrichment_count} enrichments")
        console.print(f"   - {embedding_count} embeddings")
        console.print(f"   in {repo_path}")
        console.print()
        console.print("[dim]File index will be preserved - no need to re-scan files.[/dim]")
        
        confirm = typer.confirm("Are you sure?")
        if not confirm:
            console.print("Cancelled.")
            raise typer.Exit(code=0)
    
    # Clear enrichments and embeddings
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM enrichments")
        cursor.execute("DELETE FROM embeddings")
        conn.commit()
        conn.close()
        
        console.print(f"  ✅ Deleted {enrichment_count} enrichments")
        console.print(f"  ✅ Deleted {embedding_count} embeddings")
        console.print(f"\n[green]✨ RAG data cleared for {repo_path.name}[/green]")
        console.print("[dim]Run 'llmc service restart' to begin re-enrichment.[/dim]")
    except Exception as e:
        console.print(f"[red]❌ Failed to clear data: {e}[/red]")
        raise typer.Exit(code=1)


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
    console.print("=" * 70)
    
    # Service status
    pid = state.get("pid")
    daemon_running = False
    if pid:
        try:
            os.kill(pid, 0)
            daemon_running = True
            console.print(f"Daemon: [green]🟢 running[/green] (PID {pid})")
        except OSError:
            console.print(f"Daemon: [red]🔴 stopped[/red] (stale PID {pid})")
    else:
        console.print(f"Daemon: [red]🔴 stopped[/red]")
    
    # Last cycle with human-readable time
    last_cycle = state.get("last_cycle")
    if last_cycle:
        try:
            last = datetime.fromisoformat(last_cycle)
            ago = (datetime.now(timezone.utc) - last).total_seconds()
            if ago < 60:
                ago_str = f"{int(ago)}s ago"
            elif ago < 3600:
                ago_str = f"{int(ago/60)}m ago"
            else:
                ago_str = f"{int(ago/3600)}h {int((ago%3600)/60)}m ago"
            console.print(f"Last cycle: {ago_str} | Interval: {state.get('interval', 180)}s")
        except Exception:
            pass
    
    console.print()
    
    # Per-repository detailed status
    for i, repo_str in enumerate(state["repos"]):
        repo_path = Path(repo_str)
        stats = _get_repo_stats(repo_path)
        
        # Get quality info if available
        quality_info = _get_quality_info(repo_path)
        
        # Status icon and text
        if not stats["exists"]:
            status_icon = "❌"
            status_text = "MISSING"
            status_color = "red"
        elif not stats["has_llmc"]:
            status_icon = "⚠️"
            status_text = "NOT INIT"
            status_color = "yellow"
        elif not stats["has_db"]:
            status_icon = "⚠️"
            status_text = "NO DB"
            status_color = "yellow"
        elif stats["spans"] == 0:
            status_icon = "📂"
            status_text = "EMPTY"
            status_color = "yellow"
        elif stats["enriched"] == 0:
            status_icon = "📂"
            status_text = "INDEXED"
            status_color = "blue"
        else:
            pct = (stats["enriched"] / stats["spans"] * 100) if stats["spans"] > 0 else 0
            if pct >= 100:
                status_icon = "✅"
                status_text = "READY"
                status_color = "green"
            elif pct >= 90:
                status_icon = "✅"
                status_text = f"{pct:.0f}%"
                status_color = "green"
            else:
                status_icon = "🔄"
                status_text = f"{pct:.0f}%"
                status_color = "yellow"
        
        # Calculate pending work
        pending_enrich = max(0, stats["spans"] - stats["enriched"])
        pending_embed = max(0, stats["spans"] - stats["embedded"])
        
        # Print repo header
        console.print(f"[bold cyan]{status_icon} {stats['name']}[/bold cyan] [{status_color}]{status_text}[/{status_color}]")
        
        # Stats line
        stats_parts = [
            f"files={stats.get('files', '?')}",
            f"spans={stats['spans']}",
            f"enriched={stats['enriched']}",
            f"embedded={stats['embedded']}",
        ]
        if pending_enrich > 0:
            stats_parts.append(f"[yellow]pending_enrich={pending_enrich}[/yellow]")
        if pending_embed > 0:
            stats_parts.append(f"[yellow]pending_embed={pending_embed}[/yellow]")
        console.print(f"   {', '.join(stats_parts)}")
        
        # Quality line if available
        if quality_info:
            console.print(f"   [dim]quality={quality_info}[/dim]")
        
        # Path (abbreviated)
        home = str(Path.home())
        display_path = repo_str.replace(home, "~")
        console.print(f"   [dim]{display_path}[/dim]")
        
        if i < len(state["repos"]) - 1:
            console.print()  # spacing between repos
    
    console.print()
    console.print(f"[bold]Total: {len(state['repos'])} repos[/bold]")
    
    # Helpful hints
    if not daemon_running:
        console.print("\n[yellow]💡 Start daemon: llmc service start[/yellow]")


def _get_quality_info(repo_path: Path) -> str | None:
    """Try to get quality score from last doctor run."""
    # Check for quality in the database metadata or last log
    db_path = repo_path / ".rag" / "index_v2.db"
    if not db_path.exists():
        db_path = repo_path / ".llmc" / "index_v2.db"
    if not db_path.exists():
        return None
    
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Try to get quality metrics from enrichments
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN summary IS NULL OR summary = '' THEN 1 ELSE 0 END) as empty,
                SUM(CASE WHEN summary LIKE '%placeholder%' OR summary LIKE '%TODO%' THEN 1 ELSE 0 END) as placeholder,
                SUM(CASE WHEN LENGTH(summary) < 20 AND summary IS NOT NULL AND summary != '' THEN 1 ELSE 0 END) as short
            FROM enrichments
        """)
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0] > 0:
            total, empty, placeholder, short = row
            issues = empty + placeholder + short
            quality_pct = ((total - issues) / total * 100) if total > 0 else 0
            
            issue_parts = []
            if placeholder > 0:
                issue_parts.append(f"{placeholder} placeholder")
            if empty > 0:
                issue_parts.append(f"{empty} empty")
            if short > 0:
                issue_parts.append(f"{short} short")
            
            if issue_parts:
                return f"{quality_pct:.1f}% ({', '.join(issue_parts)})"
            else:
                return f"{quality_pct:.1f}%"
    except Exception:
        pass
    
    return None


@app.command("validate")
def validate(
    path: str = typer.Argument(..., help="Path to repository to validate"),
    fix_bom: bool = typer.Option(False, "--fix-bom", help="Auto-fix BOM characters in files"),
    no_connectivity: bool = typer.Option(False, "--no-connectivity", help="Skip Ollama connectivity checks"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Show all diagnostic info"),
):
    """
    Validate repository configuration for LLMC.
    
    Checks that llmc.toml has all required sections and that
    configured backends (like Ollama) are reachable.
    
    Examples:
        llmc repo validate /path/to/repo
        llmc repo validate . --fix-bom
        llmc repo validate . --no-connectivity
    """
    from llmc.commands.repo_validator import validate_repo, print_result
    
    repo_path = Path(path).resolve()
    
    if not repo_path.exists():
        console.print(f"[red]❌ Path does not exist: {path}[/red]")
        raise typer.Exit(code=1)
    
    if not repo_path.is_dir():
        console.print(f"[red]❌ Path is not a directory: {path}[/red]")
        raise typer.Exit(code=1)
    
    result = validate_repo(
        repo_path,
        check_connectivity=not no_connectivity,
        check_models=not no_connectivity,
        fix_bom=fix_bom,
        verbose=verbose,
    )
    
    print_result(result, verbose=verbose)
    
    if not result.passed:
        raise typer.Exit(code=1)


@app.command("sync-agents")
def sync_agents(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing LLMCAGENTS.md files"),
):
    """
    Sync LLMCAGENTS.md to all registered repositories.
    
    Updates or installs the agent instructions file in every registered repo.
    Use this after updating the canonical LLMCAGENTS.md in the LLMC repo.
    
    Examples:
        llmc-cli repo sync-agents           # Install where missing
        llmc-cli repo sync-agents --force   # Update all repos
    """
    # Find canonical source
    agents_source = None
    candidates = [
        Path(__file__).parent.parent.parent / "LLMCAGENTS.md",
        Path.home() / ".llmc" / "LLMCAGENTS.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            agents_source = candidate
            break
    
    if not agents_source:
        console.print("[red]❌ Cannot find canonical LLMCAGENTS.md[/red]")
        console.print("   Expected at: llmc repo root or ~/.llmc/")
        raise typer.Exit(code=1)
    
    console.print(f"[bold]📋 Syncing LLMCAGENTS.md from: {agents_source}[/bold]")
    
    state = _get_state()
    if not state["repos"]:
        console.print("[yellow]ℹ️  No repos registered[/yellow]")
        return
    
    updated = 0
    skipped = 0
    failed = 0
    
    for repo_str in state["repos"]:
        repo_path = Path(repo_str)
        if not repo_path.exists():
            console.print(f"  [yellow]⚠️  {repo_path.name}: repo missing[/yellow]")
            failed += 1
            continue
        
        llmc_dir = repo_path / ".llmc"
        llmc_dir.mkdir(parents=True, exist_ok=True)
        agents_dest = llmc_dir / "LLMCAGENTS.md"
        
        if agents_dest.exists() and not force:
            console.print(f"  ℹ️  {repo_path.name}: already exists (use --force)")
            skipped += 1
            continue
        
        try:
            shutil.copy(agents_source, agents_dest)
            action = "updated" if agents_dest.exists() else "installed"
            console.print(f"  ✅ {repo_path.name}: {action}")
            updated += 1
        except Exception as e:
            console.print(f"  [red]❌ {repo_path.name}: {e}[/red]")
            failed += 1
    
    console.print(f"\n[bold]Summary:[/bold] {updated} updated, {skipped} skipped, {failed} failed")
