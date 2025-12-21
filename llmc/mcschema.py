#!/usr/bin/env python3
"""
mcschema - Codebase schema at a glance. Private. Local. No cloud.

Generates a compact schema of your codebase from the RAG graph,
giving LLMs (and humans) instant understanding without reading every file.

Usage:
    mcschema                  # Default output
    mcschema --json           # Machine-readable
    mcschema --hotspots 30    # More hotspots
    mcschema --terse          # Paths only, no descriptions

Output includes:
- Entry points (from pyproject.toml)
- Module breakdown with purposes
- Hotspot files (most connected) with descriptions
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import json
import sys

from rich.console import Console
import typer

from llmc.core import find_repo_root
from llmc.rag.config import index_path_for_read
from llmc.rag.database import Database
from llmc.rag.schema import SchemaGraph

console = Console()

app = typer.Typer(
    name="mcschema",
    help="Codebase schema at a glance. Private. Local. No cloud.",
    add_completion=False,
)


def _load_graph(repo_root: Path) -> SchemaGraph | None:
    """Load the schema graph if available."""
    graph_path = repo_root / ".llmc" / "rag_graph.json"
    if not graph_path.exists():
        return None
    try:
        return SchemaGraph.load(graph_path)
    except Exception:
        return None


def _get_file_descriptions(db: Database) -> dict[str, str]:
    """Get all file descriptions from database."""
    try:
        rows = db.conn.execute(
            "SELECT file_path, description FROM file_descriptions"
        ).fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception:
        return {}


def _detect_entry_points(repo_root: Path) -> list[str]:
    """Detect entry points from pyproject.toml."""
    entry_points = []
    
    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib
            with open(pyproject, "rb") as f:
                data = tomllib.load(f)
            
            # [project.scripts]
            scripts = data.get("project", {}).get("scripts", {})
            for name, target in scripts.items():
                entry_points.append(f"{name} → {target}")
            
            # [project.entry-points.console_scripts] (alternate form)
            eps = data.get("project", {}).get("entry-points", {}).get("console_scripts", {})
            for name, target in eps.items():
                if f"{name} → {target}" not in entry_points:
                    entry_points.append(f"{name} → {target}")
                    
        except Exception:
            pass
    
    return entry_points


def _compute_file_connectivity(graph: SchemaGraph) -> dict[str, int]:
    """Compute edge count per file from graph relations."""
    file_edges: dict[str, int] = defaultdict(int)
    
    for relation in graph.relations:
        # Extract file paths from entity IDs
        # Format: "sym:module.Class.method" or "file:path/to/file.py"
        for entity_id in [relation.src, relation.dst]:
            if entity_id.startswith("file:"):
                file_path = entity_id[5:]  # Remove "file:" prefix
                file_edges[file_path] += 1
            elif entity_id.startswith("sym:"):
                # Find the entity to get its file_path
                for entity in graph.entities:
                    if entity.id == entity_id and entity.file_path:
                        file_edges[entity.file_path] += 1
                        break
    
    return dict(file_edges)


def _group_by_module(files: list[str], depth: int = 2) -> dict[str, list[str]]:
    """Group files by module (first N path segments)."""
    modules: dict[str, list[str]] = defaultdict(list)
    
    for file_path in files:
        parts = Path(file_path).parts
        if len(parts) >= depth:
            module = "/".join(parts[:depth]) + "/"
        elif len(parts) == 1:
            module = "(root)"
        else:
            module = "/".join(parts[:-1]) + "/"
        modules[module].append(file_path)
    
    return dict(modules)


def _summarize_module(file_descriptions: dict[str, str], files: list[str]) -> str:
    """Generate a one-line module summary from file descriptions."""
    # Get descriptions for files in this module
    descs = [file_descriptions.get(f, "") for f in files if f in file_descriptions]
    descs = [d for d in descs if d]  # Filter empty
    
    if not descs:
        return ""
    
    # Take first sentence from first description as proxy
    first = descs[0].split(".")[0].strip()
    if len(first) > 80:
        first = first[:77] + "..."
    return first


def generate_schema(
    repo_root: Path,
    max_hotspots: int = 20,
    include_descriptions: bool = True,
) -> dict:
    """Generate compact codebase schema from RAG data."""
    
    # Load data sources
    db_path = index_path_for_read(repo_root)
    if not db_path.exists():
        raise FileNotFoundError("No RAG index found. Run: mcgrep init")
    
    db = Database(db_path)
    stats = db.stats()
    file_descriptions = _get_file_descriptions(db) if include_descriptions else {}
    
    # Get all file paths
    all_files = [row[0] for row in db.conn.execute("SELECT path FROM files").fetchall()]
    db.close()
    
    # Load graph for connectivity analysis
    graph = _load_graph(repo_root)
    
    # Compute hotspots
    if graph:
        file_connectivity = _compute_file_connectivity(graph)
        # Sort by connectivity
        sorted_files = sorted(
            file_connectivity.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        # Top 10%, capped
        hotspot_count = min(max(len(all_files) // 10, 5), max_hotspots)
        hotspots = sorted_files[:hotspot_count]
    else:
        hotspots = []
    
    # Group files by module
    modules = _group_by_module(all_files)
    
    # Build module summaries
    module_info = {}
    for module, files in sorted(modules.items(), key=lambda x: -len(x[1])):
        info = {
            "files": len(files),
        }
        if include_descriptions:
            summary = _summarize_module(file_descriptions, files)
            if summary:
                info["purpose"] = summary
        module_info[module] = info
    
    # Entry points
    entry_points = _detect_entry_points(repo_root)
    
    # Build hotspot list with descriptions
    hotspot_list = []
    for file_path, edge_count in hotspots:
        entry = {
            "file": file_path,
            "edges": edge_count,
        }
        if include_descriptions and file_path in file_descriptions:
            # First sentence only
            desc = file_descriptions[file_path].split(".")[0].strip()
            if len(desc) > 100:
                desc = desc[:97] + "..."
            entry["purpose"] = desc
        hotspot_list.append(entry)
    
    return {
        "name": repo_root.name,
        "stats": {
            "files": stats["files"],
            "spans": stats["spans"],
            "entities": len(graph.entities) if graph else 0,
            "edges": len(graph.relations) if graph else 0,
        },
        "entry_points": entry_points,
        "modules": module_info,
        "hotspots": hotspot_list,
    }


def _print_schema(schema: dict, terse: bool = False) -> None:
    """Pretty-print schema to console."""
    name = schema["name"]
    stats = schema["stats"]
    
    console.print(f"[bold cyan]# {name}[/bold cyan]")
    console.print(
        f"[dim]{stats['files']} files, {stats['spans']} spans, "
        f"{stats['entities']} entities, {stats['edges']} edges[/dim]\n"
    )
    
    # Entry points
    if schema["entry_points"]:
        console.print("[bold]entry_points:[/bold]")
        for ep in schema["entry_points"]:
            console.print(f"  - {ep}")
        console.print()
    
    # Modules (top 10 by file count)
    console.print("[bold]modules:[/bold]")
    modules = list(schema["modules"].items())[:10]
    for module, info in modules:
        file_count = info["files"]
        purpose = info.get("purpose", "")
        if terse or not purpose:
            console.print(f"  [cyan]{module}[/cyan] ({file_count} files)")
        else:
            console.print(f"  [cyan]{module}[/cyan] ({file_count} files)")
            console.print(f"    [dim]{purpose}[/dim]")
    
    if len(schema["modules"]) > 10:
        console.print(f"  [dim]... and {len(schema['modules']) - 10} more modules[/dim]")
    console.print()
    
    # Hotspots
    if schema["hotspots"]:
        console.print("[bold]hotspots:[/bold] [dim](most connected files)[/dim]")
        for hs in schema["hotspots"]:
            file_path = hs["file"]
            edges = hs["edges"]
            purpose = hs.get("purpose", "")
            
            console.print(f"  [yellow]{file_path}[/yellow] ({edges} edges)")
            if not terse and purpose:
                console.print(f"    [dim]{purpose}[/dim]")


@app.command()
def schema(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    hotspots: int = typer.Option(20, "--hotspots", "-n", help="Max hotspot files to show"),
    terse: bool = typer.Option(False, "--terse", "-t", help="Compact output, no descriptions"),
):
    """
    Generate a compact codebase schema.
    
    Shows entry points, module breakdown, and hotspot files (most connected)
    with their purposes. Perfect for LLM bootstrap context.
    
    Examples:
        mcschema                  # Default output
        mcschema --json           # Machine-readable
        mcschema --hotspots 30    # More hotspots
        mcschema --terse          # Paths only
    """
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        console.print("Run: mcgrep init")
        raise typer.Exit(1)
    
    try:
        result = generate_schema(
            repo_root,
            max_hotspots=hotspots,
            include_descriptions=not terse,
        )
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error generating schema:[/red] {e}")
        raise typer.Exit(1)
    
    if json_output:
        console.print(json.dumps(result, indent=2))
    else:
        _print_schema(result, terse=terse)


def main():
    """Entry point."""
    # Handle bare invocation as default command
    if len(sys.argv) == 1 or (len(sys.argv) > 1 and sys.argv[1].startswith("-")):
        # No subcommand, run schema directly
        pass
    app()


if __name__ == "__main__":
    main()
