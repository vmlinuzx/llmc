#!/usr/bin/env python3
"""
mcgrep - Semantic grep for code. Private. Local. No cloud.

Like mgrep, but your code never leaves your machine.

Usage:
    mcgrep "where is auth handled?"
    mcgrep "database connection" src/
    mcgrep -n 20 "error handling"
    mcgrep "router" --extract 10 --context 3
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
from llmc.rag.database import Database
from llmc.training_data import ToolCallExample, emit_training_example

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


def _normalize_result_path(repo_root: Path, raw_path: Path | str) -> Path | None:
    """Normalize a search result path to a repo-relative path when possible.

    Returns None if the path cannot be safely resolved under repo_root.
    """
    try:
        candidate = raw_path if isinstance(raw_path, Path) else Path(str(raw_path))
    except Exception:
        return None

    if candidate.is_absolute():
        try:
            return candidate.relative_to(repo_root)
        except ValueError:
            return None

    return candidate


def _merge_line_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping/adjacent (start, end) line ranges."""
    if not ranges:
        return []

    sorted_ranges = sorted(ranges, key=lambda r: (r[0], r[1]))
    merged: list[tuple[int, int]] = []
    cur_start, cur_end = sorted_ranges[0]

    for start, end in sorted_ranges[1:]:
        if start <= cur_end + 1:
            cur_end = max(cur_end, end)
            continue
        merged.append((cur_start, cur_end))
        cur_start, cur_end = start, end

    merged.append((cur_start, cur_end))
    return merged


def _emit_search_training(query: str, path: str | None, limit: int) -> None:
    """Emit OpenAI-format training data for this search.
    
    Outputs a JSON training example that can be used to fine-tune models
    on LLMC tool calling patterns.
    """
    from llmc.rag.search import search_spans
    import json

    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]", err=True)
        raise typer.Exit(1)

    # Run search to get results
    try:
        results = search_spans(query, limit=min(limit, 10), repo_root=repo_root)
    except Exception as e:
        console.print(f"[red]Search error:[/red] {e}", err=True)
        raise typer.Exit(1)

    # Build tool output (simplified version of normal output)
    output_lines = []
    for i, item in enumerate(results[:10], 1):
        file_path = str(item.path)
        start = item.start_line
        end = item.end_line
        score = item.normalized_score
        summary = item.summary or ""
        if len(summary) > 100:
            summary = summary[:97] + "..."
        output_lines.append(f"{i}. [{score:.0f}] {file_path}:{start}-{end}")
        if summary:
            output_lines.append(f"   {summary}")
    
    tool_output = "\n".join(output_lines) if output_lines else "No results found."

    # Build training example
    arguments = {"query": query}
    if path:
        arguments["path"] = path
    if limit != 10:
        arguments["limit"] = limit

    example = ToolCallExample(
        tool_name="rag_search",
        arguments=arguments,
        user_query=f"Search the codebase for: {query}",
        tool_output=tool_output,
    )

    # Output as JSON
    print(emit_training_example(example, include_schema=True))


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


def _run_search_extracted(
    query: str,
    path: str | None,
    limit: int,
    extract_count: int,
    context_lines: int,
    show_summary: bool,
) -> None:
    """Semantic search and print extracted span context (thin mode)."""
    from llmc.rag.search import search_spans

    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        console.print("Run: mcgrep init")
        raise typer.Exit(1)

    effective_limit = max(limit, extract_count)

    # Run embedding-based semantic search (same backend as default output).
    try:
        results = search_spans(query, limit=effective_limit, repo_root=repo_root)
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

    top_spans = items[:extract_count]
    groups: dict[str, list] = {}
    file_order: list[str] = []

    for item in top_spans:
        rel_path = _normalize_result_path(repo_root, item.path)
        if rel_path is None:
            continue
        file_path = str(rel_path)
        if file_path not in groups:
            groups[file_path] = []
            file_order.append(file_path)
        groups[file_path].append(item)

    if not groups:
        console.print(f"[dim]No readable results for:[/dim] {query}")
        return

    console.print(
        f"[bold]{len(top_spans)} spans in {len(groups)} files[/bold] [green]●[/green] semantic"
    )
    console.print(
        f"[dim]Mode: extract (±{context_lines} lines). Lx-y are 1-based lines; [score] is 0-100 relevance.[/dim]"
    )
    console.print("[dim]Tip: use --expand N to return full file content.[/dim]\n")

    source_cache: dict[str, list[str] | None] = {}

    for file_path in file_order:
        spans = groups.get(file_path, [])
        if not spans:
            continue

        console.print(f"[bold cyan]━━━ {file_path} ━━━[/bold cyan]")

        full_path = repo_root / file_path
        if file_path not in source_cache:
            try:
                content = full_path.read_text(errors="ignore")
                source_cache[file_path] = content.splitlines()
            except Exception as e:
                console.print(f"[red]Error reading file:[/red] {e}")
                source_cache[file_path] = None

        lines = source_cache[file_path]
        if lines is None:
            console.print()
            continue

        total_lines = len(lines)
        if total_lines == 0:
            console.print("[dim](empty file)[/dim]\n")
            continue

        expanded_ranges: list[tuple[int, int]] = []
        match_lines: set[int] = set()
        match_hints: list[str] = []

        for span in spans:
            start = int(span.start_line or 1)
            end = int(span.end_line or start)
            if start <= 0:
                start = 1
            if end < start:
                end = start

            start = min(start, total_lines)
            end = min(end, total_lines)

            for line_no in range(start, end + 1):
                match_lines.add(line_no)

            score = float(getattr(span, "normalized_score", 0.0) or 0.0)
            symbol = str(getattr(span, "symbol", "") or "").strip()
            symbol_str = f" • {symbol}" if symbol else ""
            match_hints.append(f"L{start}-{end}[{score:.0f}]{symbol_str}")

            expanded_start = max(1, start - context_lines)
            expanded_end = min(total_lines, end + context_lines)
            expanded_ranges.append((expanded_start, expanded_end))

        merged_ranges = _merge_line_ranges(expanded_ranges)
        matches_str = ", ".join(match_hints[:8])
        if len(match_hints) > 8:
            matches_str += f" (+{len(match_hints) - 8} more)"
        console.print(f"[dim]Matches: {matches_str}[/dim]\n")

        last_end: int | None = None
        for range_start, range_end in merged_ranges:
            if last_end is not None and range_start > last_end + 1:
                console.print("[dim]  ⋮[/dim]")

            for line_no in range(range_start, range_end + 1):
                try:
                    line = lines[line_no - 1]
                except Exception:
                    line = ""
                if line_no in match_lines:
                    console.print(f"[yellow]{line_no:>5}[/yellow] │ {line}")
                else:
                    console.print(f"[dim]{line_no:>5}[/dim] │ {line}")

            last_end = range_end
            console.print()

        if show_summary:
            # Summaries are a helpful hint but should stay thin.
            for span in spans[:5]:
                summary = getattr(span, "summary", None)
                if not summary:
                    continue
                summary_str = str(summary)
                if len(summary_str) > 120:
                    summary_str = summary_str[:117] + "..."
                score = float(getattr(span, "normalized_score", 0.0) or 0.0)
                console.print(f"[green]→[{score:.1f}] {summary_str}[/green]")
            console.print()


def _run_search(query: str, path: str | None, limit: int, show_summary: bool) -> None:
    """Core search logic using embedding-based semantic search.
    
    Output format (hybrid):
    1. Top files: compact (FilePath "span-summary (proxy)" : Lstart-end[score])
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

    # === PART 1: Separate CODE and DOCS files ===
    
    # Group by file - preserving order of first appearance
    code_groups: dict[str, list] = {}
    docs_groups: dict[str, list] = {}
    file_descriptions: dict[str, str] = {}

    # Get file descriptions from the database
    from llmc.rag.config import index_path_for_read
    try:
        db_path = index_path_for_read(repo_root)
    except Exception:
        db_path = repo_root / ".rag" / "index_v2.db"  # Fallback
    if db_path.exists():
        db = Database(db_path)
        rows = db.conn.execute("SELECT file_path, description FROM file_descriptions").fetchall()
        for row in rows:
            file_descriptions[row["file_path"]] = row["description"]
        db.close()
    
    DOC_EXTENSIONS = {".md", ".markdown", ".rst", ".txt"}
    
    for item in items:
        file_path = str(item.path)
        path_obj = Path(file_path)
        is_doc = path_obj.suffix.lower() in DOC_EXTENSIONS
        
        target_groups = docs_groups if is_doc else code_groups
        
        if file_path not in target_groups:
            target_groups[file_path] = []
            # Use first span's summary as file description (first sentence) if not in the db
            if file_path not in file_descriptions and item.summary:
                desc = item.summary.split('.')[0]  # First sentence
                file_descriptions[file_path] = desc
        target_groups[file_path].append(item)

    total_files = len(code_groups) + len(docs_groups)

    # Header with format explanation
    console.print(
        f"[bold]{len(items)} spans in {total_files} files[/bold] "
        f"([cyan]{len(code_groups)} code[/cyan], [green]{len(docs_groups)} docs[/green]) "
        "[green]●[/green] semantic"
    )
    console.print('[dim]Format: FilePath "summary" : Lstart-end[score][/dim]')
    console.print(
        "[dim]Legend: score is 0-100 relevance. "
        "Tip: use --extract for code context.[/dim]\n"
    )

    # Check for sidecar-eligible files (for display)
    sidecar_files: set[str] = set()
    try:
        from llmc.rag.sidecar import is_sidecar_eligible, get_sidecar_path
        for file_path in list(code_groups.keys()) + list(docs_groups.keys()):
            if is_sidecar_eligible(Path(file_path)):
                sidecar_path = get_sidecar_path(Path(file_path), repo_root)
                if sidecar_path.exists():
                    sidecar_files.add(file_path)
    except ImportError:
        pass  # Sidecar module not available

    def _print_file_group(file_path: str, spans: list) -> None:
        span_strs = []
        for s in spans[:5]:  # Max 5 spans per file
            span_strs.append(f"L{s.start_line}-{s.end_line}[{s.normalized_score:.0f}]")
        if len(spans) > 5:
            span_strs.append(f"+{len(spans)-5}more")
        
        spans_compact = ", ".join(span_strs)
        desc = file_descriptions.get(file_path, "")
        desc_str = f' "{desc}"' if desc else ""
        
        # Add sidecar indicator for PDF/DOCX files with readable sidecars
        sidecar_hint = " [dim green]📄 readable[/dim green]" if file_path in sidecar_files else ""
        
        console.print(f"[bold]{file_path}[/bold]{desc_str}{sidecar_hint} : [yellow]{spans_compact}[/yellow]")

    # === CODE section (top 20) ===
    console.print("[bold cyan]── CODE ──[/bold cyan]")
    top_code = list(code_groups.items())[:20]
    if top_code:
        for file_path, spans in top_code:
            _print_file_group(file_path, spans)
    else:
        console.print("[dim]  (no code matches)[/dim]")
    
    # === DOCS section (top 5) ===
    console.print("\n[bold green]── DOCS ──[/bold green]")
    top_docs = list(docs_groups.items())[:5]
    if top_docs:
        for file_path, spans in top_docs:
            _print_file_group(file_path, spans)
    else:
        console.print("[dim]  (no documentation matches)[/dim]")

    # === PART 2: Top 10 detailed span results (like mgrep) ===
    
    console.print(f"\n[dim]─── Top 10 spans (detailed) ───[/dim]\n")
    
    # Show top 10 spans in detail
    for i, item in enumerate(items[:10], 1):
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
    extract: int = typer.Option(
        0,
        "-x",
        "--extract",
        help="Extract top N spans as code with surrounding context (thin mode).",
    ),
    context: int = typer.Option(
        3,
        "-C",
        "--context",
        help="Context lines around spans (extract mode only).",
    ),
    expand: int = typer.Option(
        0, "-e", "--expand", help="Return full file content for top N results (LLM mode)"
    ),
    emit_training: bool = typer.Option(
        False, "--emit-training", help="Output OpenAI-format training data instead of normal output"
    ),
):
    """
    Semantic search over your codebase.

    Examples:
        mcgrep search "where is authentication handled?"
        mcgrep search "database connection" -n 20
        mcgrep search "router" --extract 10 --context 3
        mcgrep search "auth" --expand 3  # Full file content for top 3 hits
    """
    if extract < 0:
        raise typer.BadParameter("--extract must be >= 0")
    if context < 0:
        raise typer.BadParameter("--context must be >= 0")
    if extract > 0 and expand > 0:
        raise typer.BadParameter("Use either --extract or --expand, not both.")

    query_str = " ".join(query)
    
    # Training data mode - emit OpenAI-format example
    if emit_training:
        _emit_search_training(query_str, path, limit)
        return
    
    if extract > 0:
        _run_search_extracted(query_str, path, limit, extract, context, summary)
    elif expand > 0:
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
