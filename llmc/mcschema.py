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

def _get_enrichment_summaries(db: Database, file_paths: list[str]) -> dict[str, str]:
    """Get enrichment summaries for files by aggregating span summaries."""
    summaries = {}
    try:
        for file_path in file_paths:
            # Get the first enrichment summary for this file
            row = db.conn.execute(
                """SELECT e.summary FROM enrichments e
                   JOIN spans s ON s.span_hash = e.span_hash
                   WHERE s.path = ? AND e.summary IS NOT NULL
                   LIMIT 1""",
                (file_path,)
            ).fetchone()
            if row and row[0]:
                # First sentence only
                summary = row[0].split(".")[0].strip()
                if len(summary) > 100:
                    summary = summary[:97] + "..."
                summaries[file_path] = summary
    except Exception:
        pass
    return summaries


def _get_recent_activity(repo_root: Path, limit: int = 5) -> dict:
    """Get recent git activity."""
    import subprocess
    
    result = {
        "commits": [],
        "active_files": [],
    }
    
    try:
        # Recent commits
        proc = subprocess.run(
            ["git", "log", f"-{limit}", "--oneline", "--no-decorate"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            for line in proc.stdout.strip().split("\n"):
                if line:
                    parts = line.split(" ", 1)
                    if len(parts) == 2:
                        result["commits"].append({
                            "hash": parts[0],
                            "message": parts[1][:60] + ("..." if len(parts[1]) > 60 else ""),
                        })
        
        # Active files (modified in last 7 days)
        proc = subprocess.run(
            ["git", "log", "--since=7 days ago", "--name-only", "--pretty=format:"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            seen = set()
            for line in proc.stdout.strip().split("\n"):
                line = line.strip()
                if line and line.endswith(".py") and line not in seen:
                    seen.add(line)
                    if len(result["active_files"]) < 10:
                        result["active_files"].append(line)
    except Exception:
        pass
    
    return result


def _get_patterns(graph: "SchemaGraph") -> dict:
    """Get structural patterns from the graph."""
    patterns = {
        "kinds": {},
        "top_symbols": [],
    }
    
    if not graph:
        return patterns
    
    # Count entity kinds
    for entity in graph.entities:
        kind = getattr(entity, "kind", None) or "unknown"
        patterns["kinds"][kind] = patterns["kinds"].get(kind, 0) + 1
    
    # Find most connected symbols (by counting relation mentions)
    # Aggregate by short name to avoid duplicates like main() from different files
    symbol_refs = {}
    for rel in graph.relations:
        for sym_id in [rel.src, rel.dst]:
            if sym_id.startswith("sym:"):
                # Use qualified name without "sym:" prefix
                name = sym_id.removeprefix("sym:")
                # Get short name for aggregation
                short = name.split(".")[-1] if "." in name else name
                symbol_refs[short] = symbol_refs.get(short, 0) + 1
    
    # Top 5 most referenced symbols (deduplicated by short name)
    sorted_syms = sorted(symbol_refs.items(), key=lambda x: -x[1])[:5]
    for name, count in sorted_syms:
        patterns["top_symbols"].append({"name": name, "refs": count})
    
    return patterns




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

    # Check for graph staleness and auto-rebuild if needed
    # Uses JSON graph mtime vs index DB mtime (simpler, more reliable)
    try:
        graph_json_path = repo_root / ".llmc" / "rag_graph.json"
        needs_rebuild = not graph_json_path.exists()
        
        if graph_json_path.exists():
            # Compare graph file mtime to latest index file mtime
            graph_mtime = graph_json_path.stat().st_mtime
            index_max_mtime = db.conn.execute("SELECT MAX(mtime) FROM files").fetchone()[0] or 0
            if graph_mtime < index_max_mtime:
                needs_rebuild = True
        
        if needs_rebuild:
            console.print("[yellow]Graph is stale or missing. Rebuilding...[/yellow]")
            from llmc.rag_nav.tool_handlers import build_graph_for_repo
            build_graph_for_repo(repo_root)
            console.print("[green]✓[/green] Graph rebuilt.\n")
    except Exception as e:
        console.print(f"[dim]Graph rebuild skipped: {e}[/dim]")

    file_descriptions = _get_file_descriptions(db) if include_descriptions else {}
    
    # Get all file paths (keep db open for enrichment query later)
    all_files = [row[0] for row in db.conn.execute("SELECT path FROM files").fetchall()]
    
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
    
    # Get enrichment summaries for hotspot files
    hotspot_paths = [h["file"] for h in hotspot_list]
    enrichment_summaries = _get_enrichment_summaries(db, hotspot_paths) if include_descriptions else {}
    db.close()  # Done with database
    
    # Attach enrichment summaries to hotspots (prefer over file_descriptions)
    for hs in hotspot_list:
        if hs["file"] in enrichment_summaries and not hs.get("purpose"):
            hs["purpose"] = enrichment_summaries[hs["file"]]
    
    # Get recent git activity
    recent_activity = _get_recent_activity(repo_root)
    
    # Get structural patterns
    patterns = _get_patterns(graph)
    
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
        "recent_activity": recent_activity,
        "patterns": patterns,
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
    
    # Recent activity (new section)
    if not terse and schema.get("recent_activity"):
        activity = schema["recent_activity"]
        if activity.get("commits"):
            console.print()
            console.print("[bold]recent_commits:[/bold]")
            for c in activity["commits"][:5]:
                console.print(f"  [magenta]{c['hash']}[/magenta] {c['message']}")
        
        if activity.get("active_files"):
            console.print()
            console.print("[bold]active_files:[/bold] [dim](modified in last 7 days)[/dim]")
            for f in activity["active_files"][:8]:
                console.print(f"  [green]{f}[/green]")
    
    # Patterns (new section)
    if not terse and schema.get("patterns"):
        patterns = schema["patterns"]
        if patterns.get("kinds"):
            console.print()
            kinds_str = ", ".join(f"{k}: {v}" for k, v in sorted(patterns["kinds"].items(), key=lambda x: -x[1])[:5])
            console.print(f"[bold]patterns:[/bold] {kinds_str}")
        
        if patterns.get("top_symbols"):
            console.print("[bold]top_symbols:[/bold] [dim](most referenced)[/dim]")
            for sym in patterns["top_symbols"][:5]:
                console.print(f"  [blue]{sym['name']}[/blue] ({sym['refs']} refs)")


@app.command()
def schema(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    hotspots: int = typer.Option(20, "--hotspots", "-n", help="Max hotspot files to show"),
    terse: bool = typer.Option(False, "--terse", "-t", help="Compact output, no descriptions"),
):
    """
    Generate a compact codebase schema (original format).
    
    Shows entry points, module breakdown, and hotspot files (most connected)
    with their purposes. Use 'mcschema graph' for pure call graph.
    
    Examples:
        mcschema schema             # Default output
        mcschema schema --json      # Machine-readable
        mcschema schema --hotspots 30
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


@app.command()
def graph(
    limit: int = typer.Option(50, "-n", "--limit", help="Max files to show (sorted by connectivity)"),
    full: bool = typer.Option(False, "--full", "-f", help="Show ALL files (no limit)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Pure file-level call graph - minimum tokens, maximum structure.

    Files are sorted by connectivity (most connected first).
    ALL outbound calls are shown for each file.

    Format:
        file.py: "Description from enrichment"
          → dep1.py
          → dep2.py

    Examples:
        mcschema                    # Top 50 files by connectivity
        mcschema -n 100             # Top 100 files
        mcschema --full             # ALL files, no limit
    """
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        raise typer.Exit(1)
    
    # Load NetworkX graph for call relationships
    try:
        from llmc.rag.graph_nx import load_graph_nx
        G = load_graph_nx(repo_root)
    except FileNotFoundError:
        console.print("[red]Graph not found.[/red] Run: mcwho graph")
        raise typer.Exit(1)
    
    # Load file descriptions from database
    db_path = index_path_for_read(repo_root)
    file_descriptions = {}
    if db_path.exists():
        try:
            db = Database(db_path)
            file_descriptions = _get_file_descriptions(db)
            db.close()
        except Exception:
            pass
    
    # Build file→file call graph
    file_calls: dict[str, set[str]] = defaultdict(set)
    file_connectivity: dict[str, int] = defaultdict(int)
    
    for u, v, data in G.edges(data=True):
        if data.get("type") != "CALLS":
            continue
        
        u_meta = dict(G.nodes.get(u, {}))
        v_meta = dict(G.nodes.get(v, {}))
        
        u_file = u_meta.get("file_path", "")
        v_file = v_meta.get("file_path", "")
        
        # Only local-to-local calls (both have file paths)
        if u_file and v_file and u_file != v_file:
            file_calls[u_file].add(v_file)
            file_connectivity[u_file] += 1
            file_connectivity[v_file] += 1
    
    # Sort by connectivity (most connected files first)
    sorted_files = sorted(
        file_calls.keys(),
        key=lambda f: file_connectivity.get(f, 0),
        reverse=True
    )
    
    # Apply limit unless --full
    if not full:
        sorted_files = sorted_files[:limit]
    
    if json_output:
        result = {
            "repo": repo_root.name,
            "files": len(sorted_files),
            "total_files": len(file_calls),
            "edges": G.number_of_edges(),
            "graph": {}
        }
        for f in sorted_files:
            entry = {"calls": sorted(file_calls[f])}
            if f in file_descriptions:
                desc = file_descriptions[f].split(".")[0].strip()
                entry["desc"] = desc[:80] if len(desc) > 80 else desc
            result["graph"][f] = entry
        
        print(json.dumps(result, indent=2))
    else:
        console.print(f"[bold cyan]# {repo_root.name}[/bold cyan] call graph")
        console.print(f"[dim]{len(sorted_files)} files (sorted by connectivity), {G.number_of_edges()} edges[/dim]\n")
        
        for f in sorted_files:
            targets = sorted(file_calls[f])
            desc = file_descriptions.get(f, "")
            if desc:
                desc = desc.split(".")[0].strip()
                if len(desc) > 60:
                    desc = desc[:57] + "..."
                console.print(f"[yellow]{f}[/yellow]: [dim]\"{desc}\"[/dim]")
            else:
                console.print(f"[yellow]{f}[/yellow]")
            
            # Always show ALL calls - no stupid truncation
            for t in targets:
                console.print(f"  → {t}")
            console.print()


def main():
    """Entry point."""
    # Handle bare invocation - default to schema (pure call graph)
    if len(sys.argv) == 1:
        sys.argv.append("schema")
    elif len(sys.argv) > 1 and sys.argv[1].startswith("-"):
        # Flags but no subcommand - assume schema
        sys.argv.insert(1, "schema")
    app()


if __name__ == "__main__":
    main()
