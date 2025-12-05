#!/usr/bin/env python3
"""LLMC Unified CLI - Main entry point.

Reorganized into logical command groups:
- Core: init, config, tui, monitor
- service: Daemon management
- analytics: Search, stats, benchmark, graph navigation
- debug: Troubleshooting and diagnostic commands
- docs: LLMC documentation
- usertest: RUTA testing
"""


import typer

from llmc.commands import config as config_commands, service as service_commands
from llmc.commands import repo as repo_commands
from llmc.commands.init import init as init_command
from llmc.commands.rag import (
    benchmark,
    doctor,
    embed,
    enrich,
    enrich_status,
    export,
    graph,
    index,
    inspect,
    nav_lineage,
    nav_where_used,
    plan,
    search,
    stats,
    sync,
)
from llmc.commands.tui import tui
from llmc.core import LLMC_VERSION, find_repo_root, load_config

app = typer.Typer(
    name="llmc",
    help="LLMC: LLM Cost Compression & RAG Tooling",
    add_completion=True,
    no_args_is_help=True,
)

# ============================================================================
# CORE COMMANDS (Top-level essentials)
# ============================================================================
app.command(name="init")(init_command)
app.command(name="config")(config_commands.main)
app.command(name="tui")(tui)


@app.command()
def monitor():
    """Monitor service logs (alias for 'service logs -f')."""
    service_commands.logs(follow=True, lines=50)


# ============================================================================
# SERVICE GROUP - Daemon management
# ============================================================================
service_app = typer.Typer(
    help="Manage RAG service daemon",
    no_args_is_help=True,
)
service_app.command()(service_commands.start)
service_app.command()(service_commands.stop)
service_app.command()(service_commands.restart)
service_app.command()(service_commands.status)
service_app.command()(service_commands.logs)
service_app.command()(service_commands.enable)
service_app.command()(service_commands.disable)

# Nested repo management under service (legacy, kept for backwards compat)
service_repo_app = typer.Typer(
    help="Manage registered repositories (use 'llmc repo' for full features)",
    no_args_is_help=True,
)
service_repo_app.command(name="add")(service_commands.repo_add)
service_repo_app.command(name="remove")(service_commands.repo_remove)
service_repo_app.command(name="list")(service_commands.repo_list)
service_app.add_typer(service_repo_app, name="repo")

app.add_typer(service_app, name="service")


# ============================================================================
# REPO GROUP - Repository management (full-featured)
# ============================================================================
app.add_typer(repo_commands.app, name="repo")


# ============================================================================
# ANALYTICS GROUP - Search, stats, insights
# ============================================================================
analytics_app = typer.Typer(
    help="Analytics, search, and graph navigation",
    no_args_is_help=True,
)
analytics_app.command(name="search")(search)
analytics_app.command(name="stats")(stats)
analytics_app.command(name="benchmark")(benchmark)
analytics_app.command(name="where-used")(nav_where_used)
analytics_app.command(name="lineage")(nav_lineage)

app.add_typer(analytics_app, name="analytics")


# ============================================================================
# DEBUG GROUP - Troubleshooting & diagnostics
# ============================================================================
debug_app = typer.Typer(
    help="Troubleshooting and diagnostic commands",
    no_args_is_help=True,
)
debug_app.command(name="index")(index)
debug_app.command(name="doctor")(doctor)
debug_app.command(name="sync")(sync)
debug_app.command(name="enrich")(enrich)
debug_app.command(name="embed")(embed)
debug_app.command(name="graph")(graph)
debug_app.command(name="plan")(plan)
debug_app.command(name="inspect")(inspect)
debug_app.command(name="export")(export)
debug_app.command(name="enrich-status")(enrich_status)

# Nested autodoc under debug
from llmc.commands import docs as docs_commands

autodoc_app = typer.Typer(
    help="Auto-documentation generation (runs as background service)",
    no_args_is_help=True,
)
autodoc_app.command(name="generate")(docs_commands.generate)
autodoc_app.command(name="status")(docs_commands.status)
debug_app.add_typer(autodoc_app, name="autodoc")

app.add_typer(debug_app, name="debug")


# ============================================================================
# DOCS GROUP - LLMC Documentation (help/guides)
# ============================================================================
docs_app = typer.Typer(
    help="LLMC documentation and guides",
    no_args_is_help=True,
)


@docs_app.command(name="readme")
def docs_readme():
    """Display the LLMC README."""
    repo_root = find_repo_root()
    readme_path = repo_root / "README.md"
    if readme_path.exists():
        typer.echo(readme_path.read_text())
    else:
        typer.echo("README.md not found.", err=True)
        raise typer.Exit(1)


@docs_app.command(name="quickstart")
def docs_quickstart():
    """Display the quickstart guide."""
    repo_root = find_repo_root()
    quickstart_path = repo_root / "DOCS" / "QUICKSTART.md"
    if quickstart_path.exists():
        typer.echo(quickstart_path.read_text())
    else:
        # Fallback: show inline quickstart
        typer.echo("""
# LLMC Quickstart

## 1. Initialize workspace
    llmc init

## 2. Start the RAG service  
    llmc service start

## 3. Search your codebase
    llmc analytics search "your query"

## 4. Monitor enrichment progress
    llmc monitor

## 5. Check system health
    llmc debug doctor

For full documentation: llmc docs userguide
""")


@docs_app.command(name="userguide")
def docs_userguide():
    """Display the user guide or open in browser."""
    repo_root = find_repo_root()
    
    # Try several possible locations
    candidates = [
        repo_root / "DOCS" / "USERGUIDE.md",
        repo_root / "DOCS" / "CLI_REFERENCE.md",
        repo_root / "DOCS" / "README.md",
    ]
    
    for path in candidates:
        if path.exists():
            typer.echo(path.read_text())
            return
    
    typer.echo("User guide not found. Run 'llmc docs quickstart' for basic usage.", err=True)
    raise typer.Exit(1)


app.add_typer(docs_app, name="docs")


# ============================================================================
# USERTEST GROUP - RUTA testing
# ============================================================================
from llmc.commands import usertest as usertest_commands

app.add_typer(usertest_commands.app, name="usertest")


# ============================================================================
# VERSION & CALLBACK
# ============================================================================
def version_callback(value: bool):
    if value:
        root = find_repo_root()
        config = load_config(root)
        typer.echo(f"LLMC v{LLMC_VERSION}")
        typer.echo(f"Root: {root}")
        typer.echo(f"Config: {'Found' if config else 'Missing'}")
        raise typer.Exit()


@app.callback()
def common(
    ctx: typer.Context,
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, help="Show version and exit."
    ),
):
    """
    LLMC Unified CLI - Organized Command Structure
    
    Core commands: init, config, tui, monitor
    
    Command groups:
      service    - Manage the RAG daemon
      analytics  - Search, stats, benchmarks
      debug      - Troubleshooting & internals  
      docs       - Documentation & guides
      usertest   - RUTA testing framework
    """
    pass


if __name__ == "__main__":
    app()
