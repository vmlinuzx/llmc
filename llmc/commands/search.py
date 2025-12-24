"""
Unified graph-enriched search command.

This module provides the primary `llmc search` entry point that:
1. Uses FTS + reranker + graph stitch when available (the "good" path)
2. Falls back to embedding search if FTS unavailable
3. Falls back to grep if no embeddings
4. Formats output with rich graph context by default
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from llmc.core import find_repo_root


def _format_rich_item(idx: int, item: Any, show_graph: bool = True) -> str:
    """Format a single search result with rich context."""
    lines = []
    
    # Header: index + symbol + kind
    loc = item.snippet.location
    symbol_info = ""
    if hasattr(item, "symbol") and item.symbol:
        symbol_info = f" {item.symbol}"
        if hasattr(item, "kind") and item.kind:
            symbol_info += f" ({item.kind})"
    
    lines.append(f"{idx}. {loc.path}:{loc.start_line}-{loc.end_line}{symbol_info}")
    
    # Summary from enrichment (if available)
    snippet_text = item.snippet.text.strip() if item.snippet.text else ""
    if snippet_text:
        # Truncate long snippets
        if len(snippet_text) > 200:
            snippet_text = snippet_text[:200] + "..."
        lines.append(f"   {snippet_text}")
    
    # Graph context (callers/callees) if available
    if show_graph and hasattr(item, "enrichment") and item.enrichment:
        enrich = item.enrichment
        if hasattr(enrich, "callers") and enrich.callers:
            callers_str = ", ".join(enrich.callers[:3])
            lines.append(f"   Called by: {callers_str}")
        if hasattr(enrich, "callees") and enrich.callees:
            callees_str = ", ".join(enrich.callees[:3])
            lines.append(f"   Calls: {callees_str}")
    
    return "\n".join(lines)


def _format_plain_item(idx: int, item: Any) -> str:
    """Format a single search result in compact form."""
    loc = item.snippet.location
    snippet_text = item.snippet.text.strip() if item.snippet.text else ""
    if len(snippet_text) > 80:
        snippet_text = snippet_text[:80] + "..."
    
    return f"{idx}. {loc.path}:{loc.start_line}-{loc.end_line}  {snippet_text}"


def _format_json_results(result: Any) -> str:
    """Format search results as JSON."""
    payload = {
        "query": getattr(result, "query", ""),
        "source": getattr(result, "source", "UNKNOWN"),
        "freshness_state": getattr(result, "freshness_state", "UNKNOWN"),
        "items": [
            {
                "file": it.file,
                "snippet": {
                    "text": it.snippet.text,
                    "location": {
                        "path": it.snippet.location.path,
                        "start_line": it.snippet.location.start_line,
                        "end_line": it.snippet.location.end_line,
                    },
                },
            }
            for it in result.items
        ],
    }
    return json.dumps(payload, indent=2)


def _format_span_json(query: str, results: list) -> str:
    """Format span search results as JSON (embedding fallback path)."""
    payload = {
        "query": query,
        "source": "EMBEDDING_FALLBACK",
        "items": [
            {
                "score": r.score,
                "file": str(r.path),
                "line": r.start_line,
                "symbol": r.symbol,
                "kind": r.kind,
                "summary": r.summary,
            }
            for r in results
        ],
    }
    return json.dumps(payload, indent=2)


def search(
    query: str,
    limit: Annotated[int, typer.Option("-n", "--limit", help="Max results")] = 10,
    rich: Annotated[
        bool, typer.Option("--rich/--no-rich", help="Rich output with graph context")
    ] = True,
    plain: Annotated[
        bool, typer.Option("--plain", help="Minimal compact output")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output as JSON")
    ] = False,
):
    """
    Search code with graph enrichment and AI summaries.

    Uses full-text search with reranking and 1-hop graph expansion when available.
    Falls back to embedding search or grep when graph data is missing.

    Examples:
        llmc search "enrichment pipeline"
        llmc search "database connection" --limit 20
        llmc search "router" --plain
        llmc search "config" --json
    """
    from llmc.rag import tool_rag_search
    from llmc.rag.search import search_spans

    repo_root = find_repo_root()
    use_plain = plain or not rich

    # Try the rich path first (FTS + graph stitch)
    try:
        result = tool_rag_search(query, repo_root=repo_root, limit=limit)

        if json_output:
            typer.echo(_format_json_results(result))
            return

        if not result.items:
            typer.echo("No results found.")
            return

        # Show source info
        source = getattr(result, "source", "UNKNOWN")
        freshness = getattr(result, "freshness_state", "UNKNOWN")
        if not use_plain:
            typer.echo(f"[{source}] ({freshness})\n")

        for i, item in enumerate(result.items, 1):
            if use_plain:
                typer.echo(_format_plain_item(i, item))
            else:
                typer.echo(_format_rich_item(i, item))
                typer.echo()  # blank line between results

        return

    except Exception as e:
        # Log the error for debugging but continue to fallback
        import logging
        logging.getLogger(__name__).debug(f"FTS+graph search failed: {e}")

    # Fallback to embedding search
    try:
        results = search_spans(query, limit=limit, repo_root=repo_root)

        if json_output:
            typer.echo(_format_span_json(query, results))
            return

        if not results:
            typer.echo("No results found.")
            return

        if not use_plain:
            typer.echo("[EMBEDDING_FALLBACK]\n")

        for i, r in enumerate(results, 1):
            if use_plain:
                summary = r.summary[:80] + "..." if r.summary and len(r.summary) > 80 else (r.summary or "")
                typer.echo(f"{i}. {r.path}:{r.start_line}  {summary}")
            else:
                typer.echo(f"{i}. {r.path}:{r.start_line}-{r.end_line} {r.symbol or ''} ({r.kind})")
                if r.summary:
                    typer.echo(f"   {r.summary[:200]}...")
                typer.echo()

    except Exception as e:
        typer.echo(f"Search failed: {e}", err=True)
        raise typer.Exit(code=1)
