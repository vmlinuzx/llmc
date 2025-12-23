#!/usr/bin/env python3
"""LLMC Unified CLI - Main entry point.

Command groups:
- repo: Repository management (init, register, bootstrap, validate)
- service: Daemon management
- analytics: Search, stats, benchmark, graph navigation
- debug: Troubleshooting and diagnostic commands
- docs: LLMC documentation

Core commands: config, tui, monitor
"""


import re

import typer

from llmc.commands import (
    config as config_commands,
    repo as repo_commands,
    service as service_commands,
    test_mcp as test_mcp_commands,
)
from llmc.commands.rag import (
    benchmark,
    doctor,
    embed,
    enrich,
    enrich_status,
    export,
    file_descriptions,
    graph,
    index,
    inspect,
    nav_lineage,
    nav_where_used,
    plan,
    repair_logs,
    schema_check,
    search,
    stats,
    sync,
)
from llmc.commands.tui import tui
from llmc.core import LLMC_VERSION, find_repo_root, load_config

app = typer.Typer(
    name="llmc",
    help="LLMC: LLM Cost Compression & RAG Tooling",
    add_completion=False,  # Disable --install-completion/--show-completion clutter
    no_args_is_help=True,
)

# ============================================================================
# CORE COMMANDS (Top-level essentials)
# ============================================================================
app.add_typer(config_commands.app, name="config")
app.command(name="tui")(tui)
app.command(name="init")(repo_commands.init)


@app.command()
def monitor():
    """Monitor service logs (alias for 'service logs -f')."""
    service_commands.logs(follow=True, lines=50)


def _sanitize_input(text: str) -> str:
    """Sanitize input to prevent injection attacks."""
    if not text:
        return text
    # Remove potentially dangerous characters
    # ; (command chaining)
    # < > (redirection/html)
    # ' (sql/shell quotes)
    # -- (sql comments)
    pattern = r"[;<>']|--"
    return re.sub(pattern, "", text)


@app.command()
def chat(
    prompt: str = typer.Argument(None, help="Question to ask about the codebase"),
    new: bool = typer.Option(False, "-n", "--new", help="Start a new session"),
    recall: bool = typer.Option(False, "-r", "--recall", help="Show last exchange"),
    list_sessions: bool = typer.Option(
        False, "-l", "--list", help="List recent sessions"
    ),
    session_id: str = typer.Option(
        None, "-s", "--session", help="Use specific session"
    ),
    status: bool = typer.Option(False, "--status", help="Show status"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress metadata"),
    no_rag: bool = typer.Option(False, "--no-rag", help="Disable RAG search"),
    no_session: bool = typer.Option(False, "--no-session", help="Disable session"),
    model: str = typer.Option(None, "--model", help="Override model"),
):
    """AI coding assistant with RAG-powered context.

    Examples:
        llmc chat "where is the routing logic"
        llmc chat "tell me more"
        llmc chat -n "new topic"
        llmc chat -r
        llmc chat -l
    """
    import sys

    # Build args for the click CLI
    args = []
    if prompt:
        prompt = _sanitize_input(prompt)
        args.append(prompt)
    if new:
        args.append("-n")
    if recall:
        args.append("-r")
    if list_sessions:
        args.append("-l")
    if session_id:
        args.extend(["-s", session_id])
    if status:
        args.append("--status")
    if json_output:
        args.append("--json")
    if quiet:
        args.append("-q")
    if no_rag:
        args.append("--no-rag")
    if no_session:
        args.append("--no-session")
    if model:
        args.extend(["--model", model])

    # Import and run the click CLI
    from llmc_agent.cli import main as agent_main

    sys.argv = ["llmc-chat"] + args
    try:
        agent_main(standalone_mode=False)
    except SystemExit as e:
        if e.code != 0:
            raise typer.Exit(e.code)


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

# Model comparison and performance metrics
from llmc.commands.model_compare import compare_models, metrics as model_metrics

analytics_app.command(name="compare-models")(compare_models)
analytics_app.command(name="metrics")(model_metrics)

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
debug_app.command(name="file-descriptions")(file_descriptions)
debug_app.command(name="repair-logs")(repair_logs)
debug_app.command(name="schema-check")(schema_check)

app.add_typer(debug_app, name="debug")


# ============================================================================
# TESTING GROUP - RMTA and other test commands
# ============================================================================
test_app = typer.Typer(
    help="Testing and validation commands",
    no_args_is_help=True,
)
test_app.add_typer(test_mcp_commands.app, name="mcp")

app.add_typer(test_app, name="test")


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
        typer.echo(
            """
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
"""
        )


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

    typer.echo(
        "User guide not found. Run 'llmc docs quickstart' for basic usage.", err=True
    )
    raise typer.Exit(1)


# Docgen commands
from llmc.commands import docs as docs_commands

docs_app.command(name="generate")(docs_commands.generate)
docs_app.command(name="status")(docs_commands.status)

app.add_typer(docs_app, name="docs")


# NOTE: RUTA (usertest) is developer tooling for the ruthless testing army.
# Not exposed in end-user CLI. Run directly: python -m llmc.commands.usertest


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
        None,
        "--version",
        "-v",
        callback=version_callback,
        help="Show version and exit.",
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
