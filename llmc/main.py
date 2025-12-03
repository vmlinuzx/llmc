#!/usr/bin/env python3
"""LLMC Unified CLI - Main entry point."""

import typer

from llmc.commands import service as service_commands
from llmc.commands.init import init as init_command
from llmc.commands.rag import (
    benchmark,
    doctor,
    embed,
    enrich,
    export,
    graph,
    enrich_status,
    index,
    inspect,
    nav_lineage,
    nav_search,
    nav_where_used,
    plan,
    search,
    stats,
    # Phase 5: Advanced RAG
    sync,
)
from llmc.commands.tui import monitor, tui
from llmc.core import LLMC_VERSION, find_repo_root, load_config

app = typer.Typer(
    name="llmc",
    help="LLMC: LLM Cost Compression & RAG Tooling",
    add_completion=True,
    no_args_is_help=True,
)

# Core commands
app.command(name="init")(init_command)

# RAG commands (Phase 2)
app.command()(index)
app.command()(search)
app.command()(inspect)
app.command()(plan)
app.command()(stats)
app.command()(doctor)

# Advanced RAG commands (Phase 5)
app.command()(sync)
app.command()(enrich)
app.command()(embed)
app.command()(graph)
app.command()(export)
app.command()(benchmark)
app.command(name="enrich-status")(enrich_status)

# TUI commands (Phase 3)
app.command()(tui)
app.command()(monitor)

# Service management subcommand group
service_app = typer.Typer(help="Manage RAG service daemon")
service_app.command()(service_commands.start)
service_app.command()(service_commands.stop)
service_app.command()(service_commands.restart)
service_app.command()(service_commands.status)
service_app.command()(service_commands.logs)
service_app.command()(service_commands.enable)
service_app.command()(service_commands.disable)

# Nested repo management under service
repo_app = typer.Typer(help="Manage registered repositories")
repo_app.command(name="add")(service_commands.repo_add)
repo_app.command(name="remove")(service_commands.repo_remove)
repo_app.command(name="list")(service_commands.repo_list)
service_app.add_typer(repo_app, name="repo")

app.add_typer(service_app, name="service")

# Nav subcommand group (Phase 5)
nav_app = typer.Typer(help="Navigate code using RAG graph")
nav_app.command(name="search")(nav_search)
nav_app.command(name="where-used")(nav_where_used)
nav_app.command(name="lineage")(nav_lineage)

app.add_typer(nav_app, name="nav")

# Docs subcommand group (Docgen v2)
from llmc.commands import docs as docs_commands
docs_app = typer.Typer(help="Documentation generation")
docs_app.command(name="generate")(docs_commands.generate)
docs_app.command(name="status")(docs_commands.status)

app.add_typer(docs_app, name="docs")


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
    LLMC Unified CLI
    """
    pass


if __name__ == "__main__":
    app()
