#!/usr/bin/env python3
"""
mcinspect - Inspect symbols with graph context.

Usage:
    mcinspect inspect Router
    mcinspect inspect llmc.router.Router
    mcinspect inspect Router --raw         # Definition only, no graph
"""

from pathlib import Path
import typer
from rich.console import Console
import json
import sys

from llmc.core import find_repo_root
from llmc.rag.graph_ops import load_graph, get_symbol_context
from llmc.rag.inspector import inspect_symbol

console = Console()
app = typer.Typer(name="mcinspect", help="Inspect symbols with graph context.")


@app.command("inspect")
def inspect_symbol_command(
    symbol: str = typer.Argument(..., help="Symbol to inspect (e.g., Router, llmc.router.Router)"),
    raw: bool = typer.Option(False, "--raw", help="Skip graph enrichment"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Inspect a symbol with graph context."""
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        raise typer.Exit(1)

    # Get symbol definition
    definition = inspect_symbol(repo_root, symbol)
    if not definition:
        console.print(f"[red]Symbol not found:[/red] {symbol}")
        raise typer.Exit(1)

    # Get graph context
    graph_context = None
    if not raw:
        try:
            graph = load_graph(repo_root)
            graph_context = get_symbol_context(graph, symbol)
        except Exception:
            pass  # Graceful degradation

    if json_output:
        _emit_json(symbol, definition, graph_context)
    else:
        _emit_human(symbol, definition, graph_context)


def _emit_human(symbol: str, defn: dict, ctx: dict | None):
    """Human-readable output."""
    kind = defn.get("kind", "symbol")
    console.print(f"[bold cyan]━━━ {symbol} ({kind}) ━━━[/bold cyan]")
    console.print(f"File: {defn['file']}:{defn['start_line']}-{defn['end_line']}")

    if defn.get("docstring"):
        console.print(f"[dim]Purpose: {defn['docstring'][:100]}...[/dim]")

    console.print("\n[bold]Definition:[/bold]")
    console.print(f"  {defn['signature']}")

    if ctx:
        console.print("\n[bold]Graph Neighbors:[/bold]")
        if ctx.get("callers"):
            callers = ", ".join(ctx["callers"][:5])
            console.print(f"  [green]Callers ({len(ctx['callers'])}):[/green] {callers}")
        if ctx.get("callees"):
            callees = ", ".join(ctx["callees"][:5])
            console.print(f"  [blue]Callees ({len(ctx['callees'])}):[/blue] {callees}")
        if ctx.get("extends"):
            console.print(f"  [yellow]Extends:[/yellow] {ctx['extends']}")

        console.print(f"\n[dim]See also: mcwho {symbol} (for full caller/callee graph)[/dim]")


def _emit_json(symbol: str, definition: dict, graph_context: dict | None):
    """JSON output for programmatic use."""
    output = {
        "symbol": symbol,
        "definition": definition,
        "graph_context": graph_context,
    }
    print(json.dumps(output, indent=2))


def main():
    """Entry point."""
    # Handle bare symbol without 'inspect' subcommand
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-") and sys.argv[1] != "inspect":
        sys.argv.insert(1, "inspect")
    app()


if __name__ == "__main__":
    main()
