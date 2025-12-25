#!/usr/bin/env python3
"""
mchot - Find hotspot code via PageRank. Private. Local. No cloud.

Uses NetworkX graph algorithms to identify the most "important" symbols
in your codebase based on structural centrality.

Usage:
    mchot                          # Top 10 hotspots
    mchot -n 50                    # Top 50 hotspots
    mchot --json                   # JSON output for LLM context loading
    mchot --skeleton               # Generate context skeleton for LLM caching

This is ideal for:
- Identifying critical code paths
- Generating compressed codebase context for LLMs
- Finding tightly-coupled "God objects"
- 100% local operation
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table
import typer

from llmc.core import find_repo_root

console = Console()

app = typer.Typer(
    name="mchot",
    help="Find hotspot code via PageRank. Private. Local. No cloud.",
    add_completion=False,
)


def _get_graph_nx(repo_root: Path):
    """Load NetworkX graph lazily."""
    try:
        from llmc.rag.graph_nx import load_graph_nx
        return load_graph_nx(repo_root)
    except FileNotFoundError:
        console.print("[red]Graph not found.[/red] Run: mcwho graph")
        raise typer.Exit(1)
    except ImportError as e:
        console.print(f"[red]NetworkX not available:[/red] {e}")
        raise typer.Exit(1)


def _get_graph_db(repo_root: Path) -> Any | None:
    """Return GraphDatabase instance if the .db file exists (for metadata)."""
    db_path = repo_root / ".llmc" / "rag_graph.db"
    if not db_path.exists():
        return None
    try:
        from llmc.rag.graph_db import GraphDatabase
        return GraphDatabase(db_path)
    except ImportError:
        return None


def _compute_pagerank(G, top_k: int = 10) -> list[tuple[str, float]]:
    """Compute PageRank centrality scores."""
    import networkx as nx
    try:
        scores = nx.pagerank(G, alpha=0.85)
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_k]
    except Exception as e:
        console.print(f"[yellow]PageRank failed:[/yellow] {e}")
        return []


def _compute_degree_centrality(G, top_k: int = 10) -> list[tuple[str, float]]:
    """Compute in-degree centrality (who is called the most)."""
    import networkx as nx
    scores = nx.in_degree_centrality(G)
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_scores[:top_k]


def _get_node_metadata(G, node_id: str) -> dict:
    """Get node attributes from the graph."""
    if node_id in G:
        return dict(G.nodes[node_id])
    return {}


def _format_symbol_display(symbol_id: str, metadata: dict) -> str:
    """Format a symbol for display."""
    name = metadata.get("name") or symbol_id
    path = metadata.get("path") or metadata.get("file_path") or ""
    start = metadata.get("start_line") or ""
    
    # Strip 'sym:' prefix for cleaner display
    if name.startswith("sym:"):
        name = name[4:]
    if symbol_id.startswith("sym:"):
        symbol_id = symbol_id[4:]
    
    if path and start:
        return f"{name} @ {path}:{start}"
    elif path:
        return f"{name} @ {path}"
    return name if name != symbol_id else symbol_id


def _run_hotspots(
    limit: int,
    algorithm: str,
    output_json: bool,
    skeleton: bool,
    local_only: bool = False,
) -> None:
    """Main mchot logic."""
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        raise typer.Exit(1)

    G = _get_graph_nx(repo_root)
    
    # Load exclusion config from llmc.toml
    from llmc.core import load_config
    config = load_config() or {}
    schema_config = config.get("schema", {})
    exclude_prefixes = schema_config.get("exclude", [])
    
    # If local_only or has exclusions, we need to compute more and then filter
    needs_filter = local_only or exclude_prefixes
    compute_limit = limit * 20 if needs_filter else limit
    
    # Compute centrality
    if algorithm == "pagerank":
        hotspots = _compute_pagerank(G, compute_limit)
    else:
        hotspots = _compute_degree_centrality(G, compute_limit)
    
    # Filter based on local_only and exclude_prefixes
    if needs_filter:
        filtered = []
        for symbol_id, score in hotspots:
            meta = _get_node_metadata(G, symbol_id)
            # file_path is relative, path is absolute with line numbers
            path = meta.get("file_path") or meta.get("path") or ""
            
            # Skip if no path (external/stdlib) when local_only
            if local_only and not path:
                continue
            
            # Skip if path matches any exclusion prefix
            if any(path.startswith(prefix) for prefix in exclude_prefixes):
                continue
            
            filtered.append((symbol_id, score))
            if len(filtered) >= limit:
                break
        hotspots = filtered
    
    if not hotspots:
        console.print("[yellow]No hotspots found.[/yellow]")
        raise typer.Exit(0)
    
    # Enrich with metadata
    results = []
    for symbol_id, score in hotspots:
        metadata = _get_node_metadata(G, symbol_id)
        
        # The graph stores enrichments in an embedded 'metadata' dict
        embedded_meta = metadata.get("metadata", {})
        if isinstance(embedded_meta, str):
            # Sometimes it's serialized JSON
            try:
                import json as json_mod
                embedded_meta = json_mod.loads(embedded_meta)
            except Exception:
                embedded_meta = {}
        
        # Prefer file_path (relative) over path (absolute with range)
        file_path = metadata.get("file_path") or ""
        if not file_path:
            # Fall back to parsing path field
            raw_path = metadata.get("path") or ""
            if ":" in raw_path:
                file_path = raw_path.split(":")[0]
                # Strip absolute prefix
                if str(repo_root) in file_path:
                    file_path = file_path.replace(str(repo_root) + "/", "")
        
        results.append({
            "id": symbol_id,
            "score": score,
            "name": metadata.get("name") or symbol_id,
            "path": file_path,
            "kind": metadata.get("kind") or "symbol",
            "start_line": metadata.get("start_line"),
            "end_line": metadata.get("end_line"),
            # Pull enrichment from embedded metadata
            "summary": embedded_meta.get("summary"),
            "usage": embedded_meta.get("usage_guide") or embedded_meta.get("usage_snippet"),
            # Add edges for sorting
            "edges": G.in_degree(symbol_id) if symbol_id in G else 0,
        })
    
    # Sort by edges (descending) - what you see is what you sort by
    results.sort(key=lambda r: r["edges"], reverse=True)
    
    # Output modes
    if skeleton:
        _output_skeleton(repo_root, G, results)
    elif output_json:
        print(json.dumps(results, indent=2))
    else:
        _output_table(G, results, algorithm)


def _output_table(G, results: list[dict], algorithm: str) -> None:
    """Print results as a Rich table."""
    table = Table(title=f"Codebase Hotspots ({algorithm.upper()})")
    table.add_column("Symbol", style="green")
    table.add_column("Edges", style="cyan", width=6)
    table.add_column("Kind", style="dim", width=10)
    table.add_column("Location", style="dim")
    table.add_column("Summary", style="dim", max_width=50)
    
    for r in results:
        name = r["name"]
        if name.startswith("sym:"):
            name = name[4:]
        
        # Get edge count (callers)
        symbol_id = r["id"]
        edges = G.in_degree(symbol_id) if symbol_id in G else 0
        
        location = ""
        if r["path"]:
            location = f"{r['path']}"
            if r["start_line"]:
                location += f":{r['start_line']}"
        
        summary = r.get("summary") or ""
        if len(summary) > 50:
            summary = summary[:47] + "..."
        
        table.add_row(
            name,
            str(edges),
            r["kind"],
            location,
            summary,
        )
    
    console.print(table)
    console.print()
    console.print(f"[dim]Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges[/dim]")


def _load_enrichments(repo_root: Path) -> dict[str, dict]:
    """Load enrichment summaries keyed by file:line for quick lookup."""
    try:
        from llmc.rag.enrichment_db_helpers import load_enrichment_data
        enrichments = load_enrichment_data(repo_root)
        
        # Build lookup by file:start_line for fast matching
        # Store multiple key variations for robust matching
        by_location: dict[str, dict] = {}
        for span_hash, records in enrichments.items():
            for rec in records:
                if rec.file_path and rec.start_line:
                    data = {
                        "summary": rec.summary,
                        "usage_guide": rec.usage_guide,
                        "span_hash": span_hash,
                    }
                    # Store with original path
                    key = f"{rec.file_path}:{rec.start_line}"
                    by_location[key] = data
                    
                    # Also store normalized versions for matching
                    # Strip leading ./ if present
                    norm_path = rec.file_path.lstrip("./")
                    by_location[f"{norm_path}:{rec.start_line}"] = data
                    
                    # Store with llmc/ prefix for graph paths
                    if norm_path.startswith("llmc/"):
                        by_location[f"{norm_path}:{rec.start_line}"] = data
        return by_location
    except Exception:
        return {}


def _output_skeleton(repo_root: Path, G, results: list[dict]) -> None:
    """
    Generate a context skeleton for LLM caching.
    
    This produces a compact representation of the codebase's most important
    symbols, suitable for one-shot loading into LLM context with caching.
    
    Format:
    - Grouped by file
    - Includes symbol signatures/docstrings
    - Includes relationship counts
    - Includes LLM-generated enrichment summaries (the 10x crack cocaine)
    """
    import networkx as nx
    
    enriched_count = 0
    
    skeleton = {
        "repo": str(repo_root.name),
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "algorithm": "pagerank",
        "total_symbols": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "hotspots": [],
    }
    
    for r in results:
        symbol_id = r["id"]
        
        # Get neighbor counts
        in_degree = G.in_degree(symbol_id) if symbol_id in G else 0
        out_degree = G.out_degree(symbol_id) if symbol_id in G else 0
        
        # Try to load actual code snippet
        snippet = None
        if r["path"] and r["start_line"] and r["end_line"]:
            try:
                file_path = repo_root / r["path"]
                if file_path.exists():
                    lines = file_path.read_text().splitlines()
                    start = max(0, r["start_line"] - 1)
                    end = min(len(lines), r["end_line"])
                    # Limit snippet to first 10 lines (signature + docstring)
                    snippet_lines = lines[start:min(start + 10, end)]
                    snippet = "\n".join(snippet_lines)
            except Exception:
                pass
        
        entry = {
            "rank": results.index(r) + 1,
            "id": symbol_id,
            "name": r["name"].removeprefix("sym:"),
            "kind": r["kind"],
            "path": r["path"],
            "line": r["start_line"],
            "score": round(r["score"], 6),
            "callers": in_degree,
            "callees": out_degree,
        }
        
        if snippet:
            entry["snippet"] = snippet
        
        # Enrichments are already in the results from graph metadata
        if r.get("summary"):
            enriched_count += 1
            entry["summary"] = r["summary"]
        if r.get("usage"):
            entry["usage"] = r["usage"]
        
        skeleton["hotspots"].append(entry)
    
    # Group by file for better context locality
    by_file: dict[str, list] = {}
    for h in skeleton["hotspots"]:
        path = h.get("path") or "_external"
        if path not in by_file:
            by_file[path] = []
        by_file[path].append(h)
    
    skeleton["by_file"] = by_file
    skeleton["enriched_count"] = enriched_count
    skeleton["enrichment_rate"] = f"{enriched_count}/{len(results)}"
    
    print(json.dumps(skeleton, indent=2))


@app.command()
def hot(
    limit: int = typer.Option(10, "-n", "--limit", help="Number of hotspots to show"),
    algorithm: str = typer.Option(
        "pagerank", "-a", "--algorithm", 
        help="Algorithm: 'pagerank' or 'degree'"
    ),
    output_json: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    skeleton: bool = typer.Option(
        False, "--skeleton", "-s", 
        help="Generate LLM context skeleton (grouped by file, includes snippets)"
    ),
    include_all: bool = typer.Option(
        False, "--all",
        help="Include stdlib/external symbols (default: local code only)"
    ),
):
    """
    Find the most important symbols in your codebase.

    Examples:
        mchot                     # Top 10 local symbols
        mchot -n 50               # Top 50 hotspots
        mchot --all               # Include stdlib/external
        mchot --json              # JSON for scripting
        mchot --skeleton > ctx.json  # Generate LLM context cache
    """
    # local_only is the inverse of include_all
    _run_hotspots(limit, algorithm, output_json, skeleton, not include_all)


@app.command()
def path(
    source: str = typer.Argument(..., help="Source symbol"),
    target: str = typer.Argument(..., help="Target symbol"),
):
    """
    Find the shortest dependency path between two symbols.

    Examples:
        mchot path Database EnrichmentPipeline
    """
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        raise typer.Exit(1)
    
    G = _get_graph_nx(repo_root)
    import networkx as nx
    
    # Try with and without 'sym:' prefix
    candidates_src = [source, f"sym:{source}"]
    candidates_tgt = [target, f"sym:{target}"]
    
    src_id = next((c for c in candidates_src if c in G), None)
    tgt_id = next((c for c in candidates_tgt if c in G), None)
    
    if not src_id:
        console.print(f"[yellow]Source not found:[/yellow] {source}")
        raise typer.Exit(1)
    if not tgt_id:
        console.print(f"[yellow]Target not found:[/yellow] {target}")
        raise typer.Exit(1)
    
    try:
        path_nodes = nx.shortest_path(G, src_id, tgt_id)
        console.print(f"\n[bold]Shortest path ({len(path_nodes)} hops):[/bold]")
        for i, node in enumerate(path_nodes):
            prefix = "→ " if i > 0 else "  "
            display = node.removeprefix("sym:")
            meta = _get_node_metadata(G, node)
            loc = meta.get("path", "")
            if loc:
                display += f" [dim]@ {loc}[/dim]"
            console.print(f"  {prefix}{display}")
    except nx.NetworkXNoPath:
        console.print(f"[yellow]No path exists between {source} and {target}[/yellow]")
        raise typer.Exit(1)


@app.command()
def cycles():
    """
    Detect circular dependencies in the codebase.

    Examples:
        mchot cycles
    """
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        raise typer.Exit(1)
    
    G = _get_graph_nx(repo_root)
    import networkx as nx
    
    try:
        cycles_found = list(nx.simple_cycles(G))
    except Exception as e:
        console.print(f"[yellow]Cycle detection failed:[/yellow] {e}")
        raise typer.Exit(1)
    
    if not cycles_found:
        console.print("[green]✓[/green] No circular dependencies detected!")
        return
    
    console.print(f"[yellow]Found {len(cycles_found)} circular dependencies:[/yellow]\n")
    
    # Show top 10 shortest cycles
    cycles_found.sort(key=len)
    for i, cycle in enumerate(cycles_found[:10], 1):
        cycle_display = " → ".join(n.removeprefix("sym:") for n in cycle)
        console.print(f"  {i}. {cycle_display} → [dim](loop)[/dim]")
    
    if len(cycles_found) > 10:
        console.print(f"\n  [dim]... and {len(cycles_found) - 10} more cycles[/dim]")


@app.command()
def context(
    limit: int = typer.Option(50, "-n", "--limit", help="Number of hotspots to include"),
    compact: bool = typer.Option(False, "--compact", "-c", help="Compact mode (summaries only, no snippets)"),
    raw: bool = typer.Option(False, "--raw", help="Output raw JSON skeleton without wrapper text"),
):
    """
    Generate LLM-ready system context for this codebase.

    Outputs a complete system prompt with:
    - PageRank-ranked hotspots with enriched summaries
    - Behavioral guardrails to prevent random refactoring
    - Tool usage hints

    Examples:
        mchot context > system_prompt.md
        mchot context -n 100 --compact
        mchot context --raw | jq .
    """
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]", err=True)
        raise typer.Exit(1)
    
    G = _get_graph_nx(repo_root)
    
    # Compute hotspots (always local for context)
    # Over-fetch significantly since many top PageRank nodes are external (stdlib/deps)
    compute_limit = min(limit * 20, G.number_of_nodes())
    hotspots = _compute_pagerank(G, compute_limit)
    
    # Filter to local symbols
    local_hotspots = []
    for symbol_id, score in hotspots:
        meta = _get_node_metadata(G, symbol_id)
        path = meta.get("path") or meta.get("file_path") or ""
        if path:
            local_hotspots.append((symbol_id, score))
            if len(local_hotspots) >= limit:
                break
    
    # Build results with enrichments
    results = []
    for symbol_id, score in local_hotspots:
        metadata = _get_node_metadata(G, symbol_id)
        
        embedded_meta = metadata.get("metadata", {})
        if isinstance(embedded_meta, str):
            try:
                import json as json_mod
                embedded_meta = json_mod.loads(embedded_meta)
            except Exception:
                embedded_meta = {}
        
        file_path = metadata.get("file_path") or ""
        if not file_path:
            raw_path = metadata.get("path") or ""
            if ":" in raw_path:
                file_path = raw_path.split(":")[0]
                if str(repo_root) in file_path:
                    file_path = file_path.replace(str(repo_root) + "/", "")
        
        entry = {
            "name": (metadata.get("name") or symbol_id).removeprefix("sym:"),
            "kind": metadata.get("kind") or "symbol",
            "path": file_path,
            "line": metadata.get("start_line"),
            "callers": G.in_degree(symbol_id) if symbol_id in G else 0,
            "summary": embedded_meta.get("summary"),
            "usage": embedded_meta.get("usage_guide") or embedded_meta.get("usage_snippet"),
        }
        
        # Include snippet in non-compact mode
        if not compact and file_path and metadata.get("start_line"):
            try:
                fp = repo_root / file_path
                if fp.exists():
                    lines = fp.read_text().splitlines()
                    start = max(0, metadata.get("start_line") - 1)
                    end = min(len(lines), metadata.get("end_line") or start + 10)
                    entry["snippet"] = "\n".join(lines[start:min(start + 8, end)])
            except Exception:
                pass
        
        results.append(entry)
    
    # Count enrichments
    enriched = sum(1 for r in results if r.get("summary"))
    
    if raw:
        # Output raw JSON
        skeleton = {
            "repo": repo_root.name,
            "symbols": G.number_of_nodes(),
            "edges": G.number_of_edges(),
            "enriched": f"{enriched}/{len(results)}",
            "hotspots": results,
        }
        print(json.dumps(skeleton, indent=2))
        return
    
    # Generate full system prompt
    prompt_lines = [
        f"# {repo_root.name} Codebase Context",
        "",
        f"This codebase contains **{G.number_of_nodes():,}** symbols with **{G.number_of_edges():,}** relationships.",
        f"Below are the **{len(results)} most important symbols** ranked by PageRank centrality.",
        f"**{enriched}/{len(results)}** have LLM-generated summaries.",
        "",
        "## Behavioral Guardrails",
        "",
        "1. **Do not refactor code outside the user's explicit request.**",
        "2. **Use the summaries below to understand the codebase structure.**",
        "3. **When modifying code, preserve existing patterns and conventions.**",
        "4. **If uncertain about a symbol's purpose, ask before changing it.**",
        "",
        "## Available Tools",
        "",
        "- `mcgrep <query>` - Semantic search over the codebase",
        "- `mcwho <symbol>` - Find who calls/uses a symbol", 
        "- `mcinspect <symbol>` - Inspect symbol details with source",
        "- `mchot --local` - Find hotspot code via PageRank",
        "",
        "---",
        "",
        "## Top Symbols by Importance",
        "",
    ]
    
    # Add each hotspot
    for i, r in enumerate(results, 1):
        name = r["name"]
        kind = r["kind"]
        path = r["path"]
        line = r.get("line") or ""
        callers = r["callers"]
        summary = r.get("summary") or "(no summary)"
        
        location = f"`{path}:{line}`" if line else f"`{path}`"
        
        prompt_lines.append(f"### {i}. `{name}` ({kind})")
        prompt_lines.append(f"**Location:** {location} | **Callers:** {callers}")
        prompt_lines.append(f"**Summary:** {summary}")
        
        if r.get("usage"):
            prompt_lines.append(f"**Usage:** `{r['usage'][:80]}`")
        
        if r.get("snippet"):
            prompt_lines.append("```python")
            prompt_lines.append(r["snippet"])
            prompt_lines.append("```")
        
        prompt_lines.append("")
    
    prompt_lines.append("---")
    prompt_lines.append("")
    prompt_lines.append("*Generated by `mchot context` — PageRank-based codebase understanding*")
    
    print("\n".join(prompt_lines))


def main():
    """Entry point with default behavior."""
    # Handle no args - run hot command
    if len(sys.argv) == 1:
        sys.argv.append("hot")
    
    # Handle bare flags without 'hot' subcommand
    first_arg = sys.argv[1]
    known_commands = {"hot", "path", "cycles", "context"}
    help_flags = {"--help", "-h"}
    
    if first_arg in help_flags:
        pass
    elif first_arg in known_commands:
        pass
    elif first_arg.startswith("-"):
        # Flags like -n 50 or --json
        sys.argv.insert(1, "hot")
    
    app()


if __name__ == "__main__":
    main()
