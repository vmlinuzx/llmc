#!/usr/bin/env python3
"""
mcinspect - Inspect symbols with graph context.

Usage:
    mcinspect inspect Router
    mcinspect inspect llmc.router.Router
    mcinspect inspect Router --full         # Full definition
    mcinspect inspect Router --capsule      # Compact summary
    mcinspect inspect Router --json         # JSON output
"""

import json
import sys
from pathlib import Path

import typer
from rich.console import Console

from llmc.core import find_repo_root
from llmc.rag.inspector import InspectionResult, inspect_entity
from llmc.training_data import ToolCallExample, emit_training_example

console = Console()
app = typer.Typer(name="mcinspect", help="Inspect symbols with graph context.")


@app.command()
def inspect_symbol_command(
    symbol: str = typer.Argument(
        ..., help="Symbol to inspect (e.g., Router, llmc.router.Router)"
    ),
    full: bool = typer.Option(False, "--full", help="Show full definition"),
    capsule: bool = typer.Option(False, "--capsule", help="Show compact summary"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
    emit_training: bool = typer.Option(False, "--emit-training", help="Output OpenAI-format training data"),
):
    """Inspect a symbol with graph context."""
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        raise typer.Exit(1)

    # Check for graph staleness
    try:
        from llmc.rag.database import Database
        from llmc.rag.graph_db import GraphDatabase
        from llmc.rag.config import index_path_for_read
        
        index_path = index_path_for_read(repo_root)
        graph_path = repo_root / ".llmc" / "rag_graph.db"
        
        if index_path.exists() and graph_path.exists():
            with GraphDatabase(graph_path) as graph_db:
                index_db = Database(index_path)
                if graph_db.is_stale(index_db):
                    console.print("[yellow]Warning: Graph is stale. Run 'llmc-cli service restart' to update.[/yellow]")
                index_db.close()
    except Exception:
        pass  # Don't block on check failure

    try:
        result = inspect_entity(repo_root, symbol=symbol)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not result:
        console.print(f"[red]Symbol not found:[/red] {symbol}")
        raise typer.Exit(1)

    # Training data mode
    if emit_training:
        _emit_inspect_training(symbol, result)
        return

    if json_output:
        _emit_json(result)
    elif full:
        _emit_full(result)
    elif capsule:
        _emit_capsule(result)
    else:
        _emit_summary(result)


def _emit_inspect_training(symbol: str, result: InspectionResult) -> None:
    """Emit OpenAI-format training data for this inspection."""
    # Build concise output
    primary_symbol = result.defined_symbols[0] if result.defined_symbols else None
    symbol_name = primary_symbol.name if primary_symbol else symbol
    kind = primary_symbol.type if primary_symbol else "symbol"
    
    output_lines = [f"{symbol_name} ({kind}, {result.path})"]
    
    if result.file_summary:
        summary = result.file_summary
        if len(summary) > 150:
            summary = summary[:147] + "..."
        output_lines.append(f"Summary: {summary}")
    
    if result.incoming_calls:
        callers = ", ".join([c.symbol for c in result.incoming_calls[:3]])
        output_lines.append(f"Called by: {callers}")
    
    if result.outgoing_calls:
        callees = ", ".join([c.symbol for c in result.outgoing_calls[:3]])
        output_lines.append(f"Calls: {callees}")
    
    tool_output = "\n".join(output_lines)
    
    example = ToolCallExample(
        tool_name="inspect_symbol",
        arguments={"symbol": symbol},
        user_query=f"What is {symbol}?",
        tool_output=tool_output,
    )
    
    print(emit_training_example(example, include_schema=True))


def _format_size(path: str) -> tuple[int, int]:
    """Get line count and byte size."""
    try:
        p = Path(path)
        byte_size = p.stat().st_size
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            line_count = sum(1 for _ in f)
        return line_count, byte_size
    except Exception:
        return 0, 0


def _emit_summary(result: InspectionResult):
    """Human-readable summary output (default) - shows all enriched chunks."""
    primary_symbol = result.defined_symbols[0] if result.defined_symbols else None
    symbol_name = primary_symbol.name if primary_symbol else "File"
    kind = primary_symbol.type if primary_symbol else "file"
    start_line = (
        result.primary_span[0] if result.primary_span and result.primary_span[0] else 0
    )
    end_line = (
        result.primary_span[1] if result.primary_span and result.primary_span[1] else 0
    )

    console.print(
        f"[bold cyan]{symbol_name}[/bold cyan] ({kind}, {result.path}:{start_line}-{end_line})"
    )

    if result.file_summary:
        console.print(f"'{result.file_summary}'")

    # Query database for all enriched chunks for this symbol
    try:
        repo_root = find_repo_root()
        chunks = _get_enriched_chunks(repo_root, symbol_name, result.path)
        
        if chunks:
            console.print(f"\n[bold]Chunks ({len(chunks)}):[/bold]")
            for chunk in chunks:
                name = chunk['name']
                chunk_kind = chunk['kind']
                sl, el = chunk['start_line'], chunk['end_line']
                summary = chunk['summary']
                
                # Truncate summary for display
                if len(summary) > 100:
                    summary = summary[:97] + "..."
                
                console.print(f"  [yellow]{name}[/yellow] ({chunk_kind}) L{sl}-{el}")
                console.print(f"    {summary}")
    except Exception:
        pass  # Graceful degradation if DB unavailable

    if result.incoming_calls:
        callers = ", ".join([c.symbol for c in result.incoming_calls])
        console.print(f"\n[green]Called by:[/green] {callers}")
    if result.outgoing_calls:
        callees = ", ".join([c.symbol for c in result.outgoing_calls])
        console.print(f"[blue]Calls:[/blue] {callees}")

    lines, size_bytes = _format_size(result.path)
    console.print(f"\nSize: {lines} lines, {size_bytes / 1024:.1f}KB")


def _get_enriched_chunks(repo_root: Path, symbol: str, file_path: str) -> list[dict]:
    """Get all enriched chunks for a symbol from the database."""
    from llmc.rag.database import Database
    from llmc.rag.config import index_path_for_read
    
    try:
        db_path = index_path_for_read(repo_root)
    except Exception:
        db_path = repo_root / ".rag" / "index_v2.db"
    
    if not db_path.exists():
        return []
    
    db = Database(db_path)
    
    # Find spans for this symbol (parent class/function) with enrichments
    cursor = db.conn.execute('''
        SELECT s.symbol, s.kind, s.start_line, s.end_line, e.summary
        FROM spans s
        JOIN enrichments e ON s.span_hash = e.span_hash
        WHERE s.symbol LIKE ?
        AND e.summary IS NOT NULL
        ORDER BY s.start_line
    ''', (f'%{symbol}%',))
    
    chunks = []
    for row in cursor.fetchall():
        # Extract just the method name from full symbol
        full_name = row['symbol'] or ''
        name = full_name.split('.')[-1] if '.' in full_name else full_name
        
        chunks.append({
            'name': name,
            'full_name': full_name,
            'kind': row['kind'] or 'unknown',
            'start_line': row['start_line'] or 0,
            'end_line': row['end_line'] or 0,
            'summary': row['summary'] or '',
        })
    
    db.close()
    return chunks



def _emit_capsule(result: InspectionResult):
    """Ultra-compact 5-10 line output."""
    primary_symbol = result.defined_symbols[0] if result.defined_symbols else None
    symbol_name = primary_symbol.name if primary_symbol else "File"

    console.print(f"[bold cyan]{symbol_name} ({result.path})[/bold cyan]")
    if result.file_summary:
        console.print(f"Purpose: {result.file_summary}")

    if result.defined_symbols:
        exports = ", ".join([s.name for s in result.defined_symbols[:3]])
        console.print(f"Key Exports: {exports}")
    if result.incoming_calls:
        deps = ", ".join([c.symbol for c in result.incoming_calls[:3]])
        console.print(f"Dependencies: {deps}")


def _emit_full(result: InspectionResult):
    """Existing behavior for when full content is needed."""
    console.print(
        f"[bold cyan]━━━ {result.defined_symbols[0].name if result.defined_symbols else 'File'} ━━━[/bold cyan]"
    )
    console.print(f"File: {result.path}")
    console.print("\n[bold]Definition:[/bold]")
    console.print(result.snippet)


def _emit_json(result: InspectionResult):
    """JSON output for programmatic use."""
    print(json.dumps(result.to_dict(), indent=2))


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
