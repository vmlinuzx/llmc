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

app = typer.Typer(
    name="mcwho",
    help="Who uses this symbol? Private. Local. No cloud.",
    add_completion=False,
)


def _load_graph(repo_root: Path) -> tuple[list[dict], list[dict]]:
    """Load nodes and edges from .llmc/rag_graph.json."""
    graph_path = repo_root / ".llmc" / "rag_graph.json"
    if not graph_path.exists():
        return [], []
    
    try:
        with open(graph_path, encoding="utf-8") as f:
            data = json.load(f)
        
        nodes = data.get("nodes") or data.get("entities") or []
        edges = data.get("edges") or []
        
        # Handle schema_graph format
        if not edges:
            rels = data.get("relations") or data.get("schema_graph", {}).get("relations") or []
            if isinstance(rels, list):
                edges = [
                    {
                        "type": str(r.get("edge") or "").upper(),
                        "source": r.get("src") or r.get("from") or "",
                        "target": r.get("dst") or r.get("to") or "",
                    }
                    for r in rels
                ]
        
        return nodes, edges
    except Exception:
        return [], []


def _find_entity(nodes: list[dict], symbol: str) -> dict | None:
    """Find a node by symbol name (fuzzy match)."""
    symbol_lower = symbol.lower()
    
    # Exact match first
    for n in nodes:
        name = (n.get("name") or n.get("id") or "").lower()
        if name == symbol_lower:
            return n
    
    # Suffix match (e.g., "run" matches "EnrichmentPipeline.run")
    for n in nodes:
        name = (n.get("name") or n.get("id") or "").lower()
        if name.endswith(f".{symbol_lower}") or name.endswith(symbol_lower):
            return n
    
    # Contains match
    for n in nodes:
        name = (n.get("name") or n.get("id") or "").lower()
        if symbol_lower in name:
            return n
    
    return None


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
        edge_type_actual = (edge.get("type") or edge.get("edge") or "").upper()
        if edge_type_actual != edge_type.upper():
            continue
        
        source = (edge.get("source") or edge.get("src") or "").lower()
        target = (edge.get("target") or edge.get("dst") or "").lower()
        
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
        console.print(f"  [dim](none)[/dim]")
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
        console.print("Run: mcgrep init")
        raise typer.Exit(1)
    
    nodes, edges = _load_graph(repo_root)
    
    if not nodes:
        console.print("[yellow]No graph found.[/yellow]")
        console.print("Run: llmc analytics graph")
        raise typer.Exit(1)
    
    entity = _find_entity(nodes, symbol)
    
    if not entity:
        console.print(f"[yellow]Symbol not found:[/yellow] {symbol}")
        console.print(f"[dim]Searched {len(nodes)} entities in graph[/dim]")
        
        # Show closest matches
        symbol_lower = symbol.lower()
        matches = [
            n.get("name") or n.get("id") or ""
            for n in nodes
            if symbol_lower in (n.get("name") or n.get("id") or "").lower()
        ][:5]
        
        if matches:
            console.print("\n[dim]Did you mean:[/dim]")
            for m in matches:
                console.print(f"  {m}")
        
        raise typer.Exit(1)
    
    entity_id = _get_entity_id(entity)
    
    # Header
    console.print(f"\n[bold cyan]{_get_entity_display(entity)}[/bold cyan]")
    kind = entity.get("kind") or entity.get("type") or "symbol"
    console.print(f"[dim]Kind: {kind}[/dim]\n")
    
    # Default: show all if no specific flag
    show_all = not (show_callers or show_callees or show_imports)
    
    # CALLED BY (incoming CALLS edges)
    if show_all or show_callers:
        callers = _get_edges_by_type(edges, entity_id, "CALLS", "incoming")
        console.print(f"[bold green]CALLED BY[/bold green] ({len(callers)})")
        _print_edge_list(nodes, callers, "CALLED BY", limit)
        console.print()
    
    # CALLS (outgoing CALLS edges)
    if show_all or show_callees:
        callees = _get_edges_by_type(edges, entity_id, "CALLS", "outgoing")
        console.print(f"[bold yellow]CALLS[/bold yellow] ({len(callees)})")
        _print_edge_list(nodes, callees, "CALLS", limit)
        console.print()
    
    # IMPORTS (incoming/outgoing IMPORTS edges)
    if show_all or show_imports:
        imports_in = _get_edges_by_type(edges, entity_id, "IMPORTS", "incoming")
        imports_out = _get_edges_by_type(edges, entity_id, "IMPORTS", "outgoing")
        
        if imports_in:
            console.print(f"[bold blue]IMPORTED BY[/bold blue] ({len(imports_in)})")
            _print_edge_list(nodes, imports_in, "IMPORTED BY", limit)
            console.print()
        
        if imports_out:
            console.print(f"[bold blue]IMPORTS[/bold blue] ({len(imports_out)})")
            _print_edge_list(nodes, imports_out, "IMPORTS", limit)
            console.print()
    
    # Summary footer
    total_edges = len([e for e in edges if entity_id.lower() in (
        (e.get("source") or e.get("src") or "").lower(),
        (e.get("target") or e.get("dst") or "").lower()
    )])
    console.print(f"[dim]Total relationships: {total_edges} | Graph: {len(nodes)} entities, {len(edges)} edges[/dim]")


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
    
    nodes, edges = _load_graph(repo_root)
    
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
    
    console.print(f"\n[bold]Schema Graph Stats[/bold]")
    console.print(f"  Entities: {len(nodes)}")
    console.print(f"  Edges: {len(edges)}")
    
    console.print(f"\n[bold cyan]Entity Kinds:[/bold cyan]")
    for kind, count in sorted(kind_counts.items(), key=lambda x: -x[1]):
        console.print(f"  {kind}: {count}")
    
    console.print(f"\n[bold yellow]Edge Types:[/bold yellow]")
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
