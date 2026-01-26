#!/usr/bin/env python3
"""
mcread - Read files with graph context.

Like read_file, but tells you what calls it, what it imports, and what to look at next.

Usage:
    mcread read llmc/router.py
    mcread read llmc/router.py --raw          # No graph enrichment
    mcread read llmc/router.py --json         # Structured output
"""

import json
from pathlib import Path

from rich.console import Console
import typer

from llmc.core import find_repo_root
from llmc.rag.graph_ops import get_file_context, load_graph
from llmc.training_data import ToolCallExample, emit_training_example

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
    emit_training: bool = typer.Option(False, "--emit-training", help="Output OpenAI-format training data"),
):
    """Read a file with graph context.
    
    For binary documents (PDF, DOCX, etc.), automatically reads from the
    markdown sidecar if available. This makes PDFs readable by LLMs.
    """
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        raise typer.Exit(1)

    # Security: Validate path stays within repo root (prevent path traversal)
    full_path = (repo_root / file_path).resolve()
    try:
        full_path.relative_to(repo_root.resolve())
    except ValueError:
        console.print(f"[red]Security error:[/red] Path escapes repository root: {file_path}")
        raise typer.Exit(1)
    
    # Check if this is a sidecar-eligible file (PDF, DOCX, etc.)
    sidecar_content = None
    sidecar_source = None
    try:
        from llmc.rag.sidecar import get_sidecar_path, is_sidecar_eligible
        
        if is_sidecar_eligible(Path(file_path)):
            sidecar_path = get_sidecar_path(Path(file_path), repo_root)
            if sidecar_path.exists():
                import gzip
                with gzip.open(sidecar_path, "rt", encoding="utf-8") as f:
                    sidecar_content = f.read()
                sidecar_source = str(sidecar_path.relative_to(repo_root))
    except ImportError:
        pass  # Sidecar module not available
    
    # Use sidecar content if available, otherwise read original file
    if sidecar_content:
        content = sidecar_content
        content_source = f"{file_path} (via sidecar: {sidecar_source})"
    else:
        if not full_path.exists():
            console.print(f"[red]File not found:[/red] {file_path}")
            raise typer.Exit(1)
        content = full_path.read_text()
        content_source = file_path
    
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

    # Training data mode
    if emit_training:
        _emit_read_training(file_path, lines, start_line, end_line)
        return

    if json_output:
        _emit_json(file_path, lines, graph_context, sidecar_source)
    else:
        _emit_human(file_path, lines, graph_context, sidecar_source)


def _emit_read_training(
    file_path: str, lines: list[str], start_line: int | None, end_line: int | None
) -> None:
    """Emit OpenAI-format training data for this file read."""
    # Build concise output (first 20 lines or less)
    content_preview = "\n".join(lines[:20])
    if len(lines) > 20:
        content_preview += f"\n... ({len(lines) - 20} more lines)"
    
    # Build arguments
    arguments = {"path": file_path}
    if start_line:
        arguments["start_line"] = start_line
    if end_line:
        arguments["end_line"] = end_line
    
    example = ToolCallExample(
        tool_name="read_file",
        arguments=arguments,
        user_query=f"Show me the contents of {file_path}",
        tool_output=content_preview,
    )
    
    print(emit_training_example(example, include_schema=True))


def _emit_human(file_path: str, lines: list[str], ctx: dict | None, sidecar_source: str | None):
    """Human-readable output with graph context."""
    console.print(f"[bold cyan]━━━ {file_path} ━━━[/bold cyan]")
    
    # Show sidecar info if reading from converted document
    if sidecar_source:
        console.print(f"[dim green]📄 Reading from sidecar: {sidecar_source}[/dim green]")
        console.print("[dim](Original document converted to markdown for readability)[/dim]\n")

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


def _emit_json(file_path: str, lines: list[str], ctx: dict | None, sidecar_source: str | None):
    """JSON output for programmatic use."""
    output = {
        "file": file_path,
        "content": "\n".join(lines),
        "line_count": len(lines),
        "graph_context": ctx,
    }
    if sidecar_source:
        output["sidecar_source"] = sidecar_source
        output["note"] = "Content read from markdown sidecar (original document was converted)"
    print(json.dumps(output, indent=2))


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
