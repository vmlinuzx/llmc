#!/usr/bin/env python3
"""
mcgrep - Semantic grep for code. Private. Local. No cloud.

Like mgrep, but your code never leaves your machine.

Usage:
    mcgrep "where is auth handled?"
    mcgrep "database connection" src/
    mcgrep -n 20 "error handling"
    mcgrep watch                    # Start background indexer
    mcgrep status                   # Check index health

This is a thin UX wrapper around LLMC's semantic search with:
- Freshness-aware fallback (uses local search if index is stale)
- LLM-enriched summaries (not just embeddings)
- Graph-based relationship data
- 100% local operation
"""

from __future__ import annotations

from pathlib import Path
import sys

from rich.console import Console
import typer

from llmc.core import find_repo_root

console = Console()

# Create app without no_args_is_help so we can handle default behavior
app = typer.Typer(
    name="mcgrep",
    help="Semantic grep for code. Private. Local. No cloud.",
    add_completion=False,
)


def _format_source_indicator(source: str, freshness: str) -> str:
    """Format the source/freshness indicator."""
    if source == "RAG_GRAPH":
        if freshness == "FRESH":
            return "[green]●[/green] semantic"
        else:
            return "[yellow]●[/yellow] semantic (stale)"
    else:
        return "[blue]●[/blue] fallback"


def _run_search_expanded(query: str, path: str | None, limit: int, expand_count: int) -> None:
    """LLM-optimized search: find semantically, return full file content.
    
    Uses semantic search to find the right files, then returns full content
    for top N hits. This gives LLMs the broad context they need.
    """
    from llmc.rag_nav.tool_handlers import tool_rag_search

    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        console.print("Run: mcgrep init")
        raise typer.Exit(1)

    # Run semantic search
    try:
        result = tool_rag_search(repo_root, query, limit=limit)
    except FileNotFoundError:
        console.print("[red]No index found.[/red] Run: mcgrep watch")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Search error:[/red] {e}")
        raise typer.Exit(1)

    items = getattr(result, "items", []) or []

    # Filter by path if provided
    if path:
        path_filter = Path(path).resolve()
        try:
            if path_filter.is_relative_to(repo_root):
                path_filter = path_filter.relative_to(repo_root)
        except (ValueError, TypeError):
            pass
        items = [it for it in items if str(path_filter) in str(it.file)]

    if not items:
        console.print(f"[dim]No results for:[/dim] {query}")
        return

    # Deduplicate files (multiple spans might be from same file)
    seen_files: dict[str, tuple] = {}  # path -> (item, line_ranges)
    for item in items:
        loc = item.snippet.location
        file_path = str(loc.path)
        line_range = (loc.start_line, loc.end_line)
        
        if file_path not in seen_files:
            seen_files[file_path] = (item, [line_range])
        else:
            seen_files[file_path][1].append(line_range)

    # Take top N unique files
    top_files = list(seen_files.items())[:expand_count]

    console.print(f"[bold]Returning full content for {len(top_files)} files[/bold]")
    console.print(f"[dim]Query: {query}[/dim]\n")

    # Output in LLM-friendly format
    for file_path, (item, line_ranges) in top_files:
        full_path = repo_root / file_path
        
        # Header with matched line hints
        ranges_str = ", ".join(f"L{s}-{e}" for s, e in line_ranges[:3])
        if len(line_ranges) > 3:
            ranges_str += f" (+{len(line_ranges) - 3} more)"
        
        console.print(f"[bold cyan]━━━ {file_path} ━━━[/bold cyan]")
        console.print(f"[dim]Matches at: {ranges_str}[/dim]\n")
        
        # Read and output full file
        try:
            content = full_path.read_text()
            # Add line numbers for context
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                # Highlight matched lines
                is_match = any(s <= i <= e for s, e in line_ranges)
                if is_match:
                    console.print(f"[yellow]{i:>5}[/yellow] │ {line}")
                else:
                    console.print(f"[dim]{i:>5}[/dim] │ {line}")
        except Exception as e:
            console.print(f"[red]Error reading file: {e}[/red]")
        
        console.print()  # spacing between files


def _run_search(query: str, path: str | None, limit: int, show_summary: bool) -> None:
    """Core search logic using embedding-based semantic search.
    
    Output format (hybrid):
    1. Top 10 files: compact (FilePath "Desc" : spans[rank])
    2. Remaining results: detailed (one span per line with summary)
    """
    from llmc.rag.search import search_spans

    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        console.print("Run: mcgrep init")
        raise typer.Exit(1)

    # Run embedding-based semantic search (has scoring fixes for filename matching)
    try:
        # Fetch many spans to ensure we get enough unique files
        results = search_spans(query, limit=limit, repo_root=repo_root)
    except FileNotFoundError:
        console.print("[red]No index found.[/red] Run: mcgrep watch")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Search error:[/red] {e}")
        raise typer.Exit(1)

    items = results

    # Filter by path if provided
    if path:
        path_filter = Path(path).resolve()
        try:
            if path_filter.is_relative_to(repo_root):
                path_filter = path_filter.relative_to(repo_root)
        except (ValueError, TypeError):
            pass
        items = [it for it in items if str(path_filter) in str(it.path)]

    if not items:
        console.print(f"[dim]No results for:[/dim] {query}")
        return

    # === PART 1: Top 10 compact file-grouped results ===
    
    # Group by file - preserving order of first appearance
    file_groups: dict[str, list] = {}
    file_descriptions: dict[str, str] = {}
    
    for item in items:
        file_path = str(item.path)
        if file_path not in file_groups:
            file_groups[file_path] = []
            # Use first span's summary as file description (first sentence, no truncation)
            if item.summary:
                desc = item.summary.split('.')[0]  # First sentence
                file_descriptions[file_path] = desc
        file_groups[file_path].append(item)

    # Top 10 files for compact section
    top_10_files = list(file_groups.items())[:10]
    total_files = len(file_groups)

    # Header with format explanation
    console.print(f"[bold]{len(items)} spans in {total_files} files[/bold] [green]●[/green] semantic")
    console.print("[dim]FilePath \"Description\" : spans[rank][/dim]\n")

    # Compact output - one line per file (top 10)
    for file_path, spans in top_10_files:
        # Build spans string: L38-52[100], L26-35[99], ...
        span_strs = []
        for s in spans[:5]:  # Max 5 spans per file
            span_strs.append(f"L{s.start_line}-{s.end_line}[{s.normalized_score:.0f}]")
        if len(spans) > 5:
            span_strs.append(f"+{len(spans)-5}more")
        
        spans_compact = ", ".join(span_strs)
        
        # File description (no truncation)
        desc = file_descriptions.get(file_path, "")
        desc_str = f' "{desc}"' if desc else ""
        
        console.print(f"[bold]{file_path}[/bold]{desc_str} : [yellow]{spans_compact}[/yellow]")

    # === PART 2: Detailed span results (after top 10 files) ===
    
    # Get all spans NOT in top 10 files
    top_10_paths = {fp for fp, _ in top_10_files}
    remaining_items = [it for it in items if str(it.path) not in top_10_paths]
    
    if remaining_items:
        console.print(f"\n[dim]─── Remaining {len(remaining_items)} spans ───[/dim]\n")
        
        for i, item in enumerate(remaining_items, 1):
            file_path = str(item.path)
            start = item.start_line
            end = item.end_line
            score = item.normalized_score
            symbol = item.symbol or ""

            # File location with score
            symbol_str = f" • {symbol}" if symbol else ""
            console.print(
                f"[bold cyan]{i}.[/bold cyan] [{score:.1f}] [bold]{file_path}[/bold]:[yellow]{start}-{end}[/yellow]{symbol_str}"
            )

            # Enrichment summary if available
            if show_summary and item.summary:
                summary = item.summary
                if len(summary) > 120:
                    summary = summary[:117] + "..."
                console.print(f"   [green]→ {summary}[/green]")

            console.print()  # spacing


@app.command()
def search(
    query: list[str] = typer.Argument(..., help="Search query (natural language)"),
    limit: int = typer.Option(100, "-n", "-m", "--limit", help="Max spans to fetch (default: 100). Top 10 files shown in compact view."),
    path: str = typer.Option(None, "-p", "--path", help="Filter to path"),
    summary: bool = typer.Option(
        True, "--summary/--no-summary", "-s", help="Show enrichment summaries"
    ),
    expand: int = typer.Option(
        0, "-e", "--expand", help="Return full file content for top N results (LLM mode)"
    ),
):
    """
    Semantic search over your codebase.

    Examples:
        mcgrep search "where is authentication handled?"
        mcgrep search "database connection" -n 20
        mcgrep search "auth" --expand 3  # Full file content for top 3 hits
    """
    query_str = " ".join(query)
    if expand > 0:
        _run_search_expanded(query_str, path, limit, expand)
    else:
        _run_search(query_str, path, limit, summary)


@app.command()
def watch():
    """
    Start background indexer (alias for 'llmc service start').

    Keeps the semantic index updated as files change.
    """
    from llmc.commands.service import start

    console.print("[bold]Starting mcgrep watcher...[/bold]")
    start()


@app.command()
def status():
    """
    Check index health and freshness.
    """
    from llmc.rag.doctor import run_rag_doctor

    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        raise typer.Exit(1)

    report = run_rag_doctor(repo_root)

    status_val = report.get("status", "UNKNOWN")
    if status_val == "OK":
        console.print("[green]● Index healthy[/green]")
    elif status_val == "STALE":
        console.print("[yellow]● Index stale[/yellow] (results may be outdated)")
    elif status_val == "EMPTY":
        console.print("[yellow]● Index empty[/yellow] - run: mcgrep watch")
    else:
        console.print(f"[red]● {status_val}[/red]")

    # Stats
    if "spans" in report:
        console.print(f"  Files: {report.get('files', '?')}")
        console.print(f"  Spans: {report.get('spans', '?')}")
        console.print(f"  Enriched: {report.get('enriched', '?')}")
        console.print(f"  Embedded: {report.get('embedded', '?')}")

    # Pending work
    pending = report.get("pending_enrichment", 0)
    if pending > 0:
        console.print(f"  [yellow]Pending enrichment: {pending}[/yellow]")


@app.command()
def init():
    """
    Register the current directory with LLMC.

    Creates .llmc/ workspace, generates config, and starts initial index.
    Equivalent to: llmc repo register .
    """
    from llmc.commands.repo import register

    console.print("[bold]Registering repository with LLMC...[/bold]")
    register(path=".", skip_index=False, skip_enrich=True)
    console.print("\n[green]Ready![/green] Run: mcgrep watch")


@app.command()
def stop():
    """Stop the background indexer."""
    from llmc.commands.service import stop as service_stop

    service_stop()


def main():
    """Entry point with mgrep-style default behavior."""
    # Handle no args - show friendly help instead of error
    if len(sys.argv) == 1:
        console.print(
            "[bold]mcgrep[/bold] - Semantic grep for code. Private. Local. No cloud.\n"
        )
        console.print("[dim]Usage:[/dim]")
        console.print(
            '  mcgrep [green]"your query"[/green]          Search for code semantically'
        )
        console.print(
            "  mcgrep [green]status[/green]                 Check index health"
        )
        console.print(
            "  mcgrep [green]watch[/green]                  Start background indexer"
        )
        console.print(
            "  mcgrep [green]init[/green]                   Register current repo"
        )
        console.print()
        console.print("[dim]Examples:[/dim]")
        console.print('  mcgrep "authentication flow"')
        console.print('  mcgrep "database connection" --limit 10')
        console.print('  mcgrep -n 5 "error handling"')
        console.print()
        console.print("[dim]Traditional grep (for exact matches):[/dim]")
        console.print('  grep -rn "pattern" .              Recursive with line numbers')
        console.print('  grep -ri "Pattern" .              Case insensitive')
        console.print('  grep -rn --include="*.py" "x" .   Filter by file type')
        console.print()
        console.print("[dim]Run 'mcgrep --help' for full options.[/dim]")
        return

    # Handle bare query without 'search' subcommand
    # e.g., `mcgrep "my query"` instead of `mcgrep search "my query"`
    # Also handles: `mcgrep -n 5 "my query"`
    first_arg = sys.argv[1]
    known_commands = {"search", "watch", "status", "init", "stop"}
    help_flags = {"--help", "-h"}

    # If first arg is a help flag, let typer handle it
    if first_arg in help_flags:
        pass
    # If first arg is a known command, let typer handle it normally
    elif first_arg in known_commands:
        pass
    # Otherwise, insert 'search' - could be a query or a search flag like -n
    else:
        sys.argv.insert(1, "search")

    app()


if __name__ == "__main__":
    main()
