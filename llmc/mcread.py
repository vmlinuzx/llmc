#!/usr/bin/env python3
"""
mcread - Read files with graph context.

Like read_file, but tells you what calls it, what it imports, and what to look at next.

Usage:
    mcread read llmc/router.py
    mcread read llmc/router.py --raw          # No graph enrichment
    mcread read llmc/router.py --json         # Structured output
"""

from pathlib import Path
import typer
from rich.console import Console
import json
import sys

from llmc.core import find_repo_root
from llmc.rag.graph_ops import load_graph, get_file_context

console = Console()
app = typer.Typer(name="mcread", help="Read files with graph context.")


@app.command()
def read_file_command(
    file_path: str = typer.Argument(..., help="File to read"),
    raw: bool = typer.Option(False, "--raw", help="Skip graph enrichment"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
    start_line: int = typer.Option(
        None, "-s", "--start", help="Start line (1-indexed)"
    ),
    end_line: int = typer.Option(None, "-e", "--end", help="End line (1-indexed)"),
):
    """Read a file with graph context."""
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        raise typer.Exit(1)

    full_path = repo_root / file_path
    if not full_path.exists():
        console.print(f"[red]File not found:[/red] {file_path}")
        raise typer.Exit(1)

    # Read content
    content = full_path.read_text()
    lines = content.splitlines()

    # Apply line range if specified
    if start_line or end_line:
        start = (start_line or 1) - 1
        end = end_line or len(lines)
        lines = lines[start:end]

    # Get graph context (unless --raw)
    graph_context = None
    if not raw:
        try:
            graph = load_graph(repo_root)
            graph_context = get_file_context(graph, file_path)
        except Exception:
            pass  # Graceful degradation

    if json_output:
        _emit_json(file_path, lines, graph_context)
    else:
        _emit_human(file_path, lines, graph_context)


def _emit_human(file_path: str, lines: list[str], ctx: dict | None):
    """Human-readable output with graph context."""
    console.print(f"[bold cyan]━━━ {file_path} ━━━[/bold cyan]")

    if ctx:
        if ctx.get("purpose"):
            console.print(f"[dim]Purpose: {ctx['purpose']}[/dim]\n")

        console.print("[bold]Graph Context:[/bold]")

        if ctx.get("called_by"):
            console.print("  [green]Called by:[/green]")
            for caller in ctx["called_by"][:5]:
                console.print(
                    f"    {caller['file']}:{caller['symbol']} (L{caller['line']})"
                )

        if ctx.get("imports"):
            imports_str = ", ".join(ctx["imports"][:10])
            console.print(f"  [blue]Imports:[/blue] {imports_str}")

        if ctx.get("exports"):
            exports_str = ", ".join(ctx["exports"][:10])
            console.print(f"  [yellow]Exports:[/yellow] {exports_str}")

        if ctx.get("related"):
            console.print(
                f"  [magenta]Related:[/magenta] {', '.join(ctx['related'][:3])}"
            )

        console.print()

    # Print content with line numbers
    for i, line in enumerate(lines, 1):
        console.print(f"[dim]{i:>5}[/dim] │ {line}")


def _emit_json(file_path: str, lines: list[str], ctx: dict | None):
    """JSON output for programmatic use."""
    output = {
        "file": file_path,
        "content": "\n".join(lines),
        "line_count": len(lines),
        "graph_context": ctx,
    }
    print(json.dumps(output, indent=2))


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
