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
    mcschema --rich           # Include architecture signals + centrality

Output includes:
- Entry points (from pyproject.toml)
- Module breakdown with purposes
- Hotspot files (most connected) with descriptions
- Language distribution (--rich)
- Architecture signals (--rich)
- Central symbols via PageRank (--rich)
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


# =============================================================================
# NEW: Rich context helpers for LLM understanding
# =============================================================================


def _get_language_distribution(db: "Database") -> dict[str, int]:
    """Get file count by language - tells LLM the tech stack."""
    try:
        rows = db.conn.execute(
            "SELECT lang, COUNT(*) as cnt FROM files GROUP BY lang ORDER BY cnt DESC"
        ).fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception:
        return {}


def _get_architecture_signals(graph: "SchemaGraph") -> dict:
    """Extract architecture signals from graph structure.
    
    Helps LLM understand:
    - Composition vs inheritance style
    - Coupling level (avg connectivity)
    - Relation type distribution
    """
    if not graph:
        return {}
    
    signals = {}
    
    # Relation type distribution
    relation_types: dict[str, int] = {}
    for rel in graph.relations:
        edge = rel.edge.lower()
        relation_types[edge] = relation_types.get(edge, 0) + 1
    signals["relation_types"] = relation_types
    
    # Calculate average file connectivity
    file_edges: dict[str, int] = defaultdict(int)
    for entity in graph.entities:
        if entity.file_path:
            file_edges[entity.file_path] = 0  # Initialize
    
    for rel in graph.relations:
        # Count edges per file by finding which files the src/dst belong to
        for entity in graph.entities:
            if entity.id in (rel.src, rel.dst) and entity.file_path:
                file_edges[entity.file_path] += 1
    
    if file_edges:
        total_edges = sum(file_edges.values())
        avg_connectivity = total_edges / len(file_edges)
        signals["avg_file_connectivity"] = round(avg_connectivity, 1)
        signals["max_file_connectivity"] = max(file_edges.values())
    
    # Inheritance ratio: extends / calls
    # High = OOP heavy, Low = composition/functional
    extends_count = relation_types.get("extends", 0)
    calls_count = relation_types.get("calls", 0)
    if calls_count > 0:
        ratio = extends_count / calls_count
        if ratio > 0.1:
            signals["style_hint"] = "inheritance-heavy (OOP)"
        elif ratio > 0.01:
            signals["style_hint"] = "mixed (some inheritance)"
        else:
            signals["style_hint"] = "composition/functional"
    
    return signals


def _get_code_structure(graph: "SchemaGraph") -> dict:
    """Get code structure breakdown with ratios.
    
    Helps LLM understand:
    - OOP vs functional style
    - Codebase complexity
    """
    if not graph:
        return {}
    
    kinds: dict[str, int] = {}
    for entity in graph.entities:
        kind = getattr(entity, "kind", None) or "unknown"
        kinds[kind] = kinds.get(kind, 0) + 1
    
    structure = {"breakdown": kinds}
    
    # Calculate style ratio
    functions = kinds.get("function", 0)
    methods = kinds.get("method", 0)
    classes = kinds.get("class", 0)
    
    if classes > 0:
        # High ratio = more functional, low ratio = more OOP
        structure["functions_per_class"] = round((functions + methods) / classes, 1)
    
    if functions + methods > 0:
        # Method-heavy = OOP style, function-heavy = functional style
        method_ratio = methods / (functions + methods)
        structure["method_ratio"] = round(method_ratio, 2)
        if method_ratio > 0.7:
            structure["paradigm"] = "OOP-dominant"
        elif method_ratio > 0.4:
            structure["paradigm"] = "mixed"
        else:
            structure["paradigm"] = "functional-dominant"
    
    return structure


def _get_central_symbols(repo_root: Path, top_k: int = 10) -> list[dict]:
    """Get most important symbols using PageRank centrality.
    
    These are the "load-bearing" symbols - touch with care.
    Filters out test files to focus on production code.
    """
    try:
        from llmc.rag.graph_nx import load_graph_nx
        import networkx as nx
        
        G = load_graph_nx(repo_root)
        
        # PageRank for importance
        scores = nx.pagerank(G, alpha=0.85)
        
        # Sort and get top k
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        seen_files = set()  # Limit to one symbol per file for diversity
        
        for node_id, score in sorted_scores:
            # Get node metadata
            node_data = dict(G.nodes.get(node_id, {}))
            
            # Skip external/stdlib symbols (no file_path)
            file_path = node_data.get("file_path", "")
            if not file_path:
                continue
            
            # Skip test files - we want production code centrality
            if "test" in file_path.lower() or file_path.startswith("tests/"):
                continue
            
            # Diversify: one symbol per file
            if file_path in seen_files:
                continue
            seen_files.add(file_path)
            
            # Clean up the symbol name
            name = node_id
            if name.startswith("sym:"):
                name = name[4:]
            elif name.startswith("type:"):
                name = name[5:]
            
            results.append({
                "symbol": name,
                "score": round(score, 6),
                "file": file_path,
            })
            
            if len(results) >= top_k:
                break
        
        return results
    except Exception:
        return []


def _get_external_dependencies(graph: "SchemaGraph", top_k: int = 10) -> list[dict]:
    """Identify most-used external symbols (not defined in repo).
    
    Tells LLM which stdlib/library APIs are heavily used.
    Filters to focus on production code patterns.
    """
    if not graph:
        return []
    
    # Build set of locally defined symbols
    local_symbols = set()
    for entity in graph.entities:
        local_symbols.add(entity.id)
    
    # Build mapping of entity_id -> file_path for filtering
    entity_files: dict[str, str] = {}
    for entity in graph.entities:
        if entity.file_path:
            entity_files[entity.id] = entity.file_path
    
    # Count references to external symbols (excluding test files)
    external_refs: dict[str, int] = {}
    for rel in graph.relations:
        # Skip if source is from a test file
        src_file = entity_files.get(rel.src, "")
        if "test" in src_file.lower():
            continue
        
        for sym_id in [rel.dst]:  # Only count destinations as external deps
            if sym_id not in local_symbols:
                # Extract short name
                name = sym_id
                if name.startswith("sym:"):
                    name = name[4:]
                
                # Skip test-prefixed symbols
                if name.startswith("test_"):
                    continue
                
                # Get the meaningful part (module.symbol format)
                parts = name.split(".")
                if len(parts) >= 2:
                    # Keep last two parts for context (e.g., "json.loads", "Path.exists")
                    name = ".".join(parts[-2:])
                
                # Skip common builtins that aren't informative
                short = parts[-1] if parts else name
                if short in ("str", "int", "list", "dict", "len", "print", "None", "True", "False", "get", "set", "open"):
                    continue
                
                external_refs[name] = external_refs.get(name, 0) + 1
    
    # Sort by frequency
    sorted_refs = sorted(external_refs.items(), key=lambda x: -x[1])[:top_k]
    return [{"symbol": name, "refs": count} for name, count in sorted_refs]


# =============================================================================
# End of new helpers
# =============================================================================


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
    include_rich: bool = False,
) -> dict:
    """Generate compact codebase schema from RAG data.
    
    Args:
        repo_root: Repository root path
        max_hotspots: Maximum hotspot files to include
        include_descriptions: Include file/module descriptions
        include_rich: Include rich context (languages, architecture, centrality)
    """
    
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
    
    # Get language distribution (for rich mode)
    languages = _get_language_distribution(db) if include_rich else {}
    
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
    
    # Build result
    result = {
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
    
    # Add rich context if requested
    if include_rich:
        result["languages"] = languages
        result["architecture"] = _get_architecture_signals(graph)
        result["code_structure"] = _get_code_structure(graph)
        result["central_symbols"] = _get_central_symbols(repo_root, top_k=10)
        result["external_deps"] = _get_external_dependencies(graph, top_k=10)
    
    return result


def _print_schema(schema: dict, terse: bool = False, rich: bool = False) -> None:
    """Pretty-print schema to console."""
    name = schema["name"]
    stats = schema["stats"]
    
    console.print(f"[bold cyan]# {name}[/bold cyan]")
    console.print(
        f"[dim]{stats['files']} files, {stats['spans']} spans, "
        f"{stats['entities']} entities, {stats['edges']} edges[/dim]\n"
    )
    
    # Languages (rich mode)
    if rich and schema.get("languages"):
        langs = schema["languages"]
        lang_str = ", ".join(f"{k}: {v}" for k, v in list(langs.items())[:5])
        console.print(f"[bold]languages:[/bold] {lang_str}")
        console.print()
    
    # Entry points
    if schema["entry_points"]:
        console.print("[bold]entry_points:[/bold]")
        for ep in schema["entry_points"]:
            console.print(f"  - {ep}")
        console.print()
    
    # Architecture signals (rich mode)
    if rich and schema.get("architecture"):
        arch = schema["architecture"]
        console.print("[bold]architecture:[/bold]")
        if arch.get("relation_types"):
            rel_str = ", ".join(f"{k}: {v}" for k, v in arch["relation_types"].items())
            console.print(f"  relations: {rel_str}")
        if arch.get("avg_file_connectivity"):
            console.print(f"  avg_connectivity: {arch['avg_file_connectivity']} edges/file")
        if arch.get("style_hint"):
            console.print(f"  style: {arch['style_hint']}")
        console.print()
    
    # Code structure (rich mode)
    if rich and schema.get("code_structure"):
        cs = schema["code_structure"]
        console.print("[bold]code_structure:[/bold]")
        if cs.get("breakdown"):
            breakdown_str = ", ".join(f"{k}: {v}" for k, v in cs["breakdown"].items())
            console.print(f"  {breakdown_str}")
        if cs.get("paradigm"):
            console.print(f"  paradigm: {cs['paradigm']}")
        if cs.get("functions_per_class"):
            console.print(f"  functions_per_class: {cs['functions_per_class']}")
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
    
    # Central symbols (rich mode) - THE LOAD-BEARING CODE
    if rich and schema.get("central_symbols"):
        console.print()
        console.print("[bold]central_symbols:[/bold] [dim](load-bearing, touch with care)[/dim]")
        for sym in schema["central_symbols"][:10]:
            score = sym.get("score", 0)
            symbol = sym.get("symbol", "")
            file_path = sym.get("file", "")
            # Truncate long symbols
            if len(symbol) > 50:
                symbol = symbol[:47] + "..."
            console.print(f"  [red]{symbol}[/red] [dim]({file_path})[/dim]")
    
    # External dependencies (rich mode)
    if rich and schema.get("external_deps"):
        console.print()
        console.print("[bold]external_deps:[/bold] [dim](stdlib/library APIs used)[/dim]")
        for dep in schema["external_deps"][:8]:
            symbol = dep.get("symbol", "")
            refs = dep.get("refs", 0)
            console.print(f"  [magenta]{symbol}[/magenta] ({refs} refs)")
    
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
    
    # Patterns (existing section - keep for backward compat but de-emphasize in rich mode)
    if not terse and not rich and schema.get("patterns"):
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
    rich: bool = typer.Option(False, "--rich", "-r", help="Include rich context (languages, architecture, centrality)"),
):
    """
    Generate a compact codebase schema (original format).
    
    Shows entry points, module breakdown, and hotspot files (most connected)
    with their purposes. Use 'mcschema graph' for pure call graph.
    
    Examples:
        mcschema schema             # Default output
        mcschema schema --json      # Machine-readable
        mcschema schema --hotspots 30
        mcschema schema --rich      # Full context for LLMs
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
            include_rich=rich,
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
        _print_schema(result, terse=terse, rich=rich)


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



# =============================================================================
# Manifest: Complete file listing with descriptions
# =============================================================================


def _get_file_manifest(db: Database, include_tests: bool = False) -> dict[str, list[dict]]:
    """Get all CODE files grouped by directory with descriptions.
    
    Filters to actual code files (.py, .ts, .js, etc.) - excludes docs (.md).
    
    Returns:
        Dict mapping directory path to list of {file, description} dicts
    """
    # Query file descriptions joined with files to get language
    # Only include code files, not markdown/docs
    query = """
        SELECT fd.file_path, fd.description
        FROM file_descriptions fd
        JOIN files f ON fd.file_path = f.path
        WHERE f.lang IN ('python', 'typescript', 'javascript', 'tsx', 'jsx', 'go', 'rust', 'java', 'c', 'cpp', 'bash', 'shell')
        ORDER BY fd.file_path
    """
    rows = db.conn.execute(query).fetchall()
    
    # Group by directory
    manifest: dict[str, list[dict]] = {}
    
    for file_path, description in rows:
        # Skip tests if not requested
        if not include_tests and ("test" in file_path.lower() or file_path.startswith("tests/")):
            continue
        
        # Get directory
        parts = Path(file_path).parts
        if len(parts) > 1:
            directory = "/".join(parts[:-1]) + "/"
        else:
            directory = "(root)"
        
        filename = parts[-1] if parts else file_path
        
        if directory not in manifest:
            manifest[directory] = []
        
        # Truncate description to first sentence, max 60 chars
        if description:
            desc = description.split(".")[0].strip()
            if len(desc) > 60:
                desc = desc[:57] + "..."
        else:
            desc = ""
        
        manifest[directory].append({
            "file": filename,
            "desc": desc,
        })
    
    return manifest


def generate_manifest(
    repo_root: Path,
    include_tests: bool = False,
) -> dict:
    """Generate complete file manifest with descriptions."""
    
    db_path = index_path_for_read(repo_root)
    if not db_path.exists():
        raise FileNotFoundError("No RAG index found. Run: mcgrep init")
    
    db = Database(db_path)
    
    try:
        manifest = _get_file_manifest(db, include_tests=include_tests)
        
        # Get language distribution
        languages = _get_language_distribution(db)
        
        # Count files
        total_files = sum(len(files) for files in manifest.values())
        
    finally:
        db.close()
    
    return {
        "name": repo_root.name,
        "total_files": total_files,
        "directories": len(manifest),
        "languages": languages,
        "manifest": manifest,
    }


def _print_manifest(data: dict) -> None:
    """Pretty-print file manifest to console."""
    
    console.print(f"[bold cyan]# {data['name']}[/bold cyan] file manifest")
    console.print(f"[dim]{data['total_files']} files in {data['directories']} directories[/dim]")
    
    if data.get("languages"):
        lang_str = ", ".join(f"{k}: {v}" for k, v in list(data["languages"].items())[:5])
        console.print(f"[dim]languages: {lang_str}[/dim]\n")
    
    # Sort directories for consistent output
    for directory in sorted(data["manifest"].keys()):
        files = data["manifest"][directory]
        console.print(f"[bold yellow]{directory}[/bold yellow]")
        
        for f in files:
            filename = f["file"]
            desc = f.get("desc", "")
            if desc:
                console.print(f"  [cyan]{filename}[/cyan] - [dim]{desc}[/dim]")
            else:
                console.print(f"  [cyan]{filename}[/cyan]")
        console.print()


@app.command()
def manifest(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    include_tests: bool = typer.Option(False, "--tests", "-t", help="Include test files"),
):
    """
    Complete file manifest with descriptions - the full codebase map.
    
    Lists every code file with its purpose, grouped by directory.
    Ideal for giving LLMs complete codebase understanding on startup.
    
    Examples:
        mcschema manifest              # Production files only
        mcschema manifest --tests      # Include test files
        mcschema manifest --json       # Machine-readable
    """
    try:
        repo_root = find_repo_root()
    except Exception:
        console.print("[red]Not in an LLMC-indexed repository.[/red]")
        raise typer.Exit(1)
    
    try:
        data = generate_manifest(repo_root, include_tests=include_tests)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error generating manifest:[/red] {e}")
        raise typer.Exit(1)
    
    if json_output:
        console.print(json.dumps(data, indent=2))
    else:
        _print_manifest(data)


def main():
    """Entry point."""
    # Handle bare invocation - default to schema subcommand
    # But allow explicit subcommands like 'manifest', 'graph'
    known_subcommands = {"schema", "graph", "manifest"}
    
    if len(sys.argv) == 1:
        # Bare invocation -> default to schema
        sys.argv.append("schema")
    elif len(sys.argv) > 1:
        first_arg = sys.argv[1]
        # If first arg is a flag (not a subcommand), insert schema
        if first_arg.startswith("-") and first_arg not in ("--help", "-h"):
            sys.argv.insert(1, "schema")
        # If --help with no subcommand, show full app help
        elif first_arg in ("--help", "-h"):
            pass  # Let typer handle it
    app()


if __name__ == "__main__":
    main()
