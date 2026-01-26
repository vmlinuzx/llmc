#!/usr/bin/env python3
"""
mcwho - Who uses this symbol? Private. Local. No cloud.

Like mcgrep, but for relationships instead of search.

Usage:
    mcwho EnrichmentPipeline.run      # Who calls this?
    mcwho Database                    # Where is this used?
    mcwho --callers foo               # Just show callers
    mcwho --callees bar               # Just show what bar calls

This is a thin UX wrapper around LLMC's schema graph with:
- Automatic symbol resolution (fuzzy matching)
- Callers, callees, imports in one output
- Thin by default, rich on request
- 100% local operation
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

from rich.console import Console
import typer

from llmc.core import find_repo_root

console = Console()

def _get_graph_db(repo_root: Path) -> Any | None:
    """Return GraphDatabase instance if the .db file exists."""
    db_path = repo_root / ".llmc" / "rag_graph.db"
    if not db_path.exists():
        return None
    try:
        from llmc.rag.graph_db import GraphDatabase
        return GraphDatabase(db_path)
    except ImportError:
        return None

app = typer.Typer(
    name="mcwho",
    help="Who uses this symbol? Private. Local. No cloud.",
    add_completion=False,
)


def _load_graph(repo_root: Path) -> dict[str, list[dict]]:
    """Load graph data from .llmc/rag_graph.json."""
    graph_path = repo_root / ".llmc" / "rag_graph.json"
    if not graph_path.exists():
        return {"entities": [], "relations": []}

    try:
        with open(graph_path, encoding="utf-8") as f:
            data = json.load(f)

        # Adapt old and new graph formats to a consistent structure
        entities = data.get("entities", data.get("nodes", []))
        relations = data.get("relations", [])

        if not relations and "edges" in data:  # Handle old edge format
            relations = [
                {
                    "edge": edge.get("type", "").lower(),
                    "src": edge.get("source"),
                    "dst": edge.get("target"),
                }
                for edge in data["edges"]
            ]

        return {"entities": entities, "relations": relations}
    except Exception:
        return {"entities": [], "relations": []}


def _get_entity_id(node: dict) -> str:
    """Get canonical ID for a node."""
    return node.get("id") or node.get("name") or ""


def _get_entity_display(node: dict) -> str:
    """Get display name for a node."""
    name = node.get("name") or node.get("id") or "?"
    path = node.get("path") or node.get("file_path") or ""
    start = node.get("start_line") or node.get("span", {}).get("start_line") or ""
    end = node.get("end_line") or node.get("span", {}).get("end_line") or ""
    
    if path and start:
        return f"{name} @ {path}:{start}-{end}"
    elif path:
        return f"{name} @ {path}"
    return name


def _get_edges_by_type(
    edges: list[dict], 
    entity_id: str, 
    edge_type: str,
    direction: str = "incoming"
) -> list[dict]:
    """Get edges of a specific type targeting (incoming) or from (outgoing) an entity."""
    results = []
    entity_id_lower = entity_id.lower()
    
    for edge in edges:
        edge_type_actual = (edge.get("edge") or edge.get("type") or "").upper()
        if edge_type_actual != edge_type.upper():
            continue

        source = (edge.get("src") or edge.get("source") or "").lower()
        target = (edge.get("dst") or edge.get("target") or "").lower()

        if direction == "incoming" and target == entity_id_lower:
            results.append(edge)
        elif direction == "outgoing" and source == entity_id_lower:
            results.append(edge)

    return results


def _resolve_node_name(nodes: list[dict], node_id: str) -> str:
    """Resolve a node ID to a readable name."""
    for n in nodes:
        if (n.get("id") or "").lower() == node_id.lower():
            name = n.get("name") or node_id
            path = n.get("path") or n.get("file_path") or ""
            start = n.get("start_line") or ""
            if path and start:
                return f"{path}:{start} → {name}"
            elif path:
                return f"{path} → {name}"
            return name
    return node_id


def _print_edge_list(
    nodes: list[dict],
    edges: list[dict],
    title: str,
    max_show: int = 10
) -> None:
    """Print a list of edges with resolved names."""
    if not edges:
        console.print("  [dim](none)[/dim]")
        return
    
    for i, edge in enumerate(edges[:max_show]):
        source = edge.get("source") or edge.get("src") or ""
        target = edge.get("target") or edge.get("dst") or ""
        
        # For incoming edges, show source; for outgoing, show target
        other_id = source if "CALLED BY" in title or "IMPORTED BY" in title else target
        resolved = _resolve_node_name(nodes, other_id)
        
        console.print(f"  {resolved}")
    
    if len(edges) > max_show:
        console.print(f"  [dim]... and {len(edges) - max_show} more[/dim]")


def _run_who(
    symbol: str,
    show_callers: bool,
    show_callees: bool,
    show_imports: bool,
    limit: int,
) -> None:
    """Main mcwho logic."""
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        console.print("Run: mcwho graph")
        raise typer.Exit(1)
    
    graph_db = _get_graph_db(repo_root)
    
    if graph_db:
        # DB Path: O(1) lookups
        with graph_db:
            # Try exact match first
            nodes = graph_db.get_nodes_by_name(symbol)
            if not nodes:
                # Try fuzzy search in DB
                nodes = graph_db.search_nodes(symbol, limit=5)
            
            if not nodes:
                console.print(f"[yellow]Symbol not found in database:[/yellow] {symbol}")
                raise typer.Exit(1)
            
            # Use the best match
            entity_node = nodes[0]
            entity_id = entity_node.id
            entity_dict = entity_node._asdict()
            
            # Header
            console.print(f"\n[bold cyan]{_get_entity_display(entity_dict)}[/bold cyan]")
            kind = entity_node.kind or "symbol"
            console.print(f"[dim]Kind: {kind}[/dim]\n")
            
            show_all = not (show_callers or show_callees or show_imports)
            
            def _print_db_edges(title: str, edge_type: str, direction: str):
                if direction == "incoming":
                    edges = graph_db.get_edges_to(entity_id, edge_type)
                else:
                    edges = graph_db.get_edges_from(entity_id, edge_type)
                
                console.print(f"[bold]{title}[/bold] ({len(edges)})")
                if not edges:
                    console.print("  [dim](none)[/dim]")
                else:
                    for edge in edges[:limit]:
                        other_id = edge.source if direction == "incoming" else edge.target
                        other_node = graph_db.get_node(other_id)
                        if other_node:
                            console.print(f"  {_get_entity_display(other_node._asdict())}")
                        else:
                            console.print(f"  {other_id} [dim](unresolved)[/dim]")
                    if len(edges) > limit:
                        console.print(f"  [dim]... and {len(edges) - limit} more[/dim]")
                console.print()

            if show_all or show_callers:
                _print_db_edges("CALLED BY", "CALLS", "incoming")
            if show_all or show_callees:
                _print_db_edges("CALLS", "CALLS", "outgoing")
            if show_all or show_imports:
                _print_db_edges("IMPORTED BY", "IMPORTS", "incoming")
                _print_db_edges("IMPORTS", "IMPORTS", "outgoing")
            
            total_edges = graph_db.edge_count() # Simplified for DB path
            console.print(f"[dim]Graph: {graph_db.node_count()} entities, {total_edges} edges | Source: SQLite[/dim]")
            return

    # Legacy JSON Path: slow linear scans
    graph_data = _load_graph(repo_root)
    nodes = graph_data["entities"]
    edges = graph_data["relations"]


@app.command()
def who(
    symbol: str = typer.Argument(..., help="Symbol to look up (function, class, method)"),
    callers: bool = typer.Option(False, "--callers", "-c", help="Show only callers"),
    callees: bool = typer.Option(False, "--callees", "-C", help="Show only callees"),
    imports: bool = typer.Option(False, "--imports", "-i", help="Show only imports"),
    limit: int = typer.Option(10, "-n", "--limit", help="Max items per section"),
):
    """
    Find who uses a symbol.

    Examples:
        mcwho EnrichmentPipeline.run
        mcwho Database --callers
        mcwho -n 20 router
    """
    _run_who(symbol, callers, callees, imports, limit)


@app.command()
def graph():
    """
    Build/rebuild the schema graph.

    Alias for: llmc analytics graph
    """
    from llmc.rag_nav.tool_handlers import build_graph_for_repo
    
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        raise typer.Exit(1)
    
    console.print("[bold]Building schema graph...[/bold]")
    build_graph_for_repo(repo_root)
    console.print("[green]✓[/green] Graph built: .llmc/rag_graph.json")


@app.command()
def stats():
    """
    Show graph statistics.
    """
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        raise typer.Exit(1)
    
    graph_data = _load_graph(repo_root)
    nodes = graph_data["entities"]
    edges = graph_data["relations"]
    
    if not nodes:
        console.print("[yellow]No graph found.[/yellow] Run: mcwho graph")
        raise typer.Exit(1)
    
    # Count edge types
    edge_counts: dict[str, int] = {}
    for e in edges:
        edge_type = (e.get("type") or e.get("edge") or "UNKNOWN").upper()
        edge_counts[edge_type] = edge_counts.get(edge_type, 0) + 1
    
    # Count entity kinds
    kind_counts: dict[str, int] = {}
    for n in nodes:
        kind = n.get("kind") or n.get("type") or "unknown"
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    
    console.print("\n[bold]Schema Graph Stats[/bold]")
    console.print(f"  Entities: {len(nodes)}")
    console.print(f"  Edges: {len(edges)}")
    
    console.print("\n[bold cyan]Entity Kinds:[/bold cyan]")
    for kind, count in sorted(kind_counts.items(), key=lambda x: -x[1]):
        console.print(f"  {kind}: {count}")
    
    console.print("\n[bold yellow]Edge Types:[/bold yellow]")
    for edge_type, count in sorted(edge_counts.items(), key=lambda x: -x[1]):
        console.print(f"  {edge_type}: {count}")


def main():
    """Entry point with mcgrep-style default behavior."""
    # Handle no args - show friendly help
    if len(sys.argv) == 1:
        console.print(
            "[bold]mcwho[/bold] - Who uses this symbol? Private. Local. No cloud.\n"
        )
        console.print("[dim]Usage:[/dim]")
        console.print(
            '  mcwho [green]"symbol"[/green]           Find who calls/uses a symbol'
        )
        console.print(
            "  mcwho [green]graph[/green]              Build/rebuild schema graph"
        )
        console.print(
            "  mcwho [green]stats[/green]              Show graph statistics"
        )
        console.print()
        console.print("[dim]Examples:[/dim]")
        console.print('  mcwho EnrichmentPipeline.run')
        console.print('  mcwho Database --callers')
        console.print('  mcwho -n 5 router')
        console.print()
        console.print("[dim]Run 'mcwho --help' for full options.[/dim]")
        return

    # Handle bare symbol without 'who' subcommand
    first_arg = sys.argv[1]
    known_commands = {"who", "graph", "stats"}
    help_flags = {"--help", "-h"}

    if first_arg in help_flags:
        pass
    elif first_arg in known_commands:
        pass
    else:
        # Treat as symbol lookup
        sys.argv.insert(1, "who")

    app()


if __name__ == "__main__":
    main()
