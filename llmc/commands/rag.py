import json
from pathlib import Path

import typer

from llmc.core import find_repo_root
from tools.rag.config import get_est_tokens_per_span, index_path_for_read
from tools.rag.database import Database
from tools.rag.doctor import run_rag_doctor as run_doctor

# Imports from existing tools
from tools.rag.indexer import index_repo as run_index_repo
from tools.rag.inspector import inspect_entity as run_inspect_entity
from tools.rag.planner import generate_plan as run_generate_plan
from tools.rag.search import search_spans as run_search_spans


def index(
    since: str | None = typer.Option(None, help="Only parse files changed since the given commit"),
    no_export: bool = typer.Option(False, help="Skip JSONL span export"),
):
    """Index the repository (full or incremental)."""
    try:
        stats = run_index_repo(since=since, export_json=not no_export)
        typer.echo(
            f"Indexed {stats['files']} files, {stats['spans']} spans in {stats.get('duration_sec', 0):.2f}s "
            f"(skipped={stats.get('skipped',0)}, unchanged={stats.get('unchanged',0)})"
        )
    except Exception as e:
        typer.echo(f"Error indexing repo: {e}", err=True)
        raise typer.Exit(code=1)

def search(
    query: str,
    limit: int = typer.Option(10, help="Max results"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Semantic search."""
    repo_root = find_repo_root()
    try:
        results = run_search_spans(query, limit=limit, repo_root=repo_root)
        if json_output:
            data = [
                {
                    "score": r.score,
                    "file": str(r.file_path),
                    "line": r.start_line,
                    "text": r.text,
                    "symbol": r.symbol
                }
                for r in results
            ]
            typer.echo(json.dumps(data, indent=2))
        else:
            for r in results:
                typer.echo(f"[{r.score:.2f}] {r.file_path}:{r.start_line} {r.symbol or ''}")
                typer.echo(f"    {r.text[:100]}...")
    except Exception as e:
        typer.echo(f"Error searching: {e}", err=True)
        raise typer.Exit(code=1)

def inspect(
    symbol: str | None = typer.Option(None, "--symbol", "-s", help="Symbol to inspect"),
    path: str | None = typer.Option(None, "--path", "-p", help="File path"),
    line: int | None = typer.Option(None, "--line", "-l", help="Line number"),
    full: bool = typer.Option(False, "--full", help="Include full source code"),
):
    """Deep dive into symbol/file."""
    repo_root = find_repo_root()
    if not symbol and not path:
        typer.echo("Must provide --symbol or --path")
        raise typer.Exit(code=1)
    
    try:
        result = run_inspect_entity(
            repo_root=repo_root,
            symbol=symbol,
            path=path,
            line=line,
            include_full_source=full
        )
        typer.echo(result) 
    except Exception as e:
        typer.echo(f"Error inspecting: {e}", err=True)
        raise typer.Exit(code=1)

def plan(
    query: str,
    limit: int = typer.Option(50, help="Max files/spans"),
    min_confidence: float = typer.Option(0.6, help="Minimum confidence threshold"),
):
    """Generate retrieval plan."""
    repo_root = find_repo_root()
    try:
        result = run_generate_plan(
            query=query,
            limit=limit,
            min_confidence=min_confidence,
            repo_root=repo_root
        )
        typer.echo(result)
    except Exception as e:
        typer.echo(f"Error planning: {e}", err=True)
        raise typer.Exit(code=1)

def stats(
    json_output: bool = typer.Option(False, "--json", help="Emit stats as JSON."),
):
    """Print summary stats for the current index."""
    repo_root = find_repo_root()
    db_file = index_path_for_read(repo_root)
    if not db_file.exists():
        typer.echo("No index database found. Run `llmc index` first.")
        return
    
    db = Database(db_file)
    try:
        info = db.stats()
    finally:
        db.close()
        
    est_tokens = get_est_tokens_per_span(repo_root)
    estimated_remote_tokens = info["spans"] * est_tokens
    
    data = {
        "repo": repo_root.name,
        "files": info["files"],
        "spans": info["spans"],
        "embeddings": info["embeddings"],
        "enrichments": info["enrichments"],
        "estimated_remote_tokens": estimated_remote_tokens,
    }
    
    if json_output:
        typer.echo(json.dumps(data, indent=2))
    else:
        typer.echo(f"Repo: {data['repo']}")
        typer.echo(f"Files: {data['files']}")
        typer.echo(f"Spans: {data['spans']}")
        typer.echo(f"Embeddings: {data['embeddings']}")
        typer.echo(f"Enrichments: {data['enrichments']}")
        typer.echo(f"Est. Remote Tokens: {data['estimated_remote_tokens']:,}")

def doctor(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Diagnose RAG health."""
    repo_root = find_repo_root()
    run_doctor(repo_path=repo_root, verbose=verbose)


# Phase 5: Advanced RAG Commands

def sync(
    paths: list[str] | None = typer.Option(None, "--path", help="Specific file paths to sync"),
    since: str | None = typer.Option(None, help="Sync files changed since commit"),
    stdin: bool = typer.Option(False, "--stdin", help="Read paths from stdin"),
):
    """Incrementally update spans for selected files."""
    from tools.rag.indexer import sync_paths
    from tools.rag.utils import git_changed_paths
    
    repo_root = find_repo_root()
    
    # Determine which files to sync
    path_list = []
    if since:
        path_list = git_changed_paths(repo_root, since)
    elif paths:
        path_list = [Path(p) for p in paths]
    elif stdin:
        import sys
        for line in sys.stdin:
            line = line.strip()
            if line:
                path_list.append(Path(line))
    
    if not path_list:
        typer.echo("No paths to sync. Use --path, --since, or --stdin")
        raise typer.Exit(code=1)
    
    try:
        stats = sync_paths(path_list)
        typer.echo(
            f"Synced {stats['files']} files, {stats['spans']} spans, "
            f"deleted={stats.get('deleted',0)}, unchanged={stats.get('unchanged',0)} "
            f"in {stats['duration_sec']:.2f}s"
        )
    except Exception as e:
        typer.echo(f"Error syncing: {e}", err=True)
        raise typer.Exit(code=1)


def enrich(
    limit: int = typer.Option(10, help="Max spans to enrich"),
    dry_run: bool = typer.Option(False, help="Preview work items without running LLM"),
    model: str = typer.Option("local-qwen", help="Model identifier"),
    cooldown: int = typer.Option(0, help="Skip spans changed within N seconds"),
):
    """Preview or execute enrichment tasks (summary/tags)."""
    from tools.rag.workers import default_enrichment_callable, enrichment_plan, execute_enrichment
    
    repo_root = find_repo_root()
    db_file = index_path_for_read(repo_root)
    if not db_file.exists():
        typer.echo("No index database found. Run `llmc index` first.")
        raise typer.Exit(code=1)
    
    db = Database(db_file)
    try:
        if dry_run:
            plan = enrichment_plan(db, repo_root, limit=limit, cooldown_seconds=cooldown)
            if not plan:
                typer.echo("No spans pending enrichment.")
                return
            typer.echo(json.dumps(plan, indent=2, ensure_ascii=False))
            typer.echo("\n(Dry run only. Remove --dry-run to persist enrichment results.)")
            return
        
        llm = default_enrichment_callable(model)
        successes, errors = execute_enrichment(
            db, repo_root, llm, limit=limit, model=model, cooldown_seconds=cooldown
        )
    finally:
        db.close()
    
    if successes:
        typer.echo(f"✅ Stored enrichment metadata for {successes} spans using {model}")
    else:
        typer.echo("No spans enriched.")
    
    if errors:
        for err in errors:
            typer.echo(f"❌ ERROR: {err}", err=True)
        raise typer.Exit(code=1)


def embed(
    limit: int = typer.Option(10, help="Max spans to embed"),
    dry_run: bool = typer.Option(False, help="Preview work items without generating embeddings"),
    model: str = typer.Option("auto", help="Embedding model (auto uses configured default)"),
    dim: int = typer.Option(0, help="Embedding dimension (0 uses model default)"),
):
    """Preview or execute embedding jobs for spans."""
    from tools.rag.workers import embedding_plan, execute_embeddings
    
    repo_root = find_repo_root()
    db_file = index_path_for_read(repo_root)
    if not db_file.exists():
        typer.echo("No index database found. Run `llmc index` first.")
        raise typer.Exit(code=1)
    
    db = Database(db_file)
    try:
        model_arg = None if model == "auto" else model
        dim_arg = None if dim <= 0 else dim
        
        if dry_run:
            plan = embedding_plan(db, repo_root, limit=limit, model=model_arg, dim=dim_arg)
            if not plan:
                typer.echo("No spans pending embedding.")
                return
            typer.echo(json.dumps(plan, indent=2, ensure_ascii=False))
            typer.echo("\n(Dry run only. Remove --dry-run to persist embeddings.)")
            return
        
        results, used_model, used_dim = execute_embeddings(
            db, repo_root, limit=limit, model=model_arg, dim=dim_arg
        )
    finally:
        db.close()
    
    if not results:
        typer.echo("No spans pending embedding.")
    else:
        typer.echo(f"✅ Stored embeddings for {len(results)} spans using {used_model} (dim={used_dim})")


def graph(
    require_enrichment: bool = typer.Option(True, help="Require enrichment data in index"),
    output: Path | None = typer.Option(None, help="Output path (default: .llmc/rag_graph.json)"),
):
    """Build a schema graph for the current repository."""
    from tools.rag.schema import build_graph_for_repo as schema_build_graph_for_repo
    
    repo_root = find_repo_root()
    
    # Default output location
    if output is None:
        llmc_dir = repo_root / ".llmc"
        llmc_dir.mkdir(parents=True, exist_ok=True)
        output = llmc_dir / "rag_graph.json"
    
    try:
        graph_obj = schema_build_graph_for_repo(
            repo_root,
            require_enrichment=require_enrichment,
        )
    except RuntimeError as err:
        typer.echo(str(err), err=True)
        raise typer.Exit(code=1)
    except FileNotFoundError as err:
        typer.echo(str(err), err=True)
        raise typer.Exit(code=1)
    
    graph_obj.save(output)
    typer.echo(f"✅ Wrote graph JSON to {output}")


def export(
    output: str | None = typer.Option(None, "-o", "--output", help="Output archive path"),
):
    """Export all RAG data to tar.gz archive."""
    from tools.rag.export_data import run_export
    
    repo_root = find_repo_root()
    output_path = Path(output) if output else None
    run_export(repo_root=repo_root, output_path=output_path)


def benchmark(
    json_output: bool = typer.Option(False, "--json", help="Emit metrics as JSON"),
    top1_threshold: float = typer.Option(0.75, help="Minimum top-1 accuracy required"),
    margin_threshold: float = typer.Option(0.1, help="Minimum avg positive-minus-negative margin"),
):
    """Run a lightweight embedding quality benchmark."""
    from tools.rag.benchmark import run_embedding_benchmark
    
    metrics = run_embedding_benchmark()
    success = metrics["top1_accuracy"] >= top1_threshold and metrics["avg_margin"] >= margin_threshold
    
    report = {
        **metrics,
        "top1_threshold": top1_threshold,
        "margin_threshold": margin_threshold,
        "passed": success,
    }
    
    if json_output:
        typer.echo(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        typer.echo("Embedding benchmark results:")
        typer.echo(f"  cases           : {int(report['cases'])}")
        typer.echo(f"  top1_accuracy   : {report['top1_accuracy']:.3f} (threshold {top1_threshold:.2f})")
        typer.echo(f"  avg_margin      : {report['avg_margin']:.3f} (threshold {margin_threshold:.2f})")
        typer.echo(f"  avg_positive    : {report['avg_positive_score']:.3f}")
        typer.echo(f"  avg_negative    : {report['avg_negative_score']:.3f}")
        typer.echo(f"  status          : {'✅ PASS' if success else '❌ FAIL'}")
    
    if not success:
        raise typer.Exit(code=1)


# Nav subcommand group
def nav_search(
    query: str,
    limit: int = typer.Option(10, "-n", "--limit", help="Max results"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output"),
):
    """Semantic/structural search using graph when fresh, else local fallback."""
    from tools.rag import tool_rag_search
    
    repo_root = find_repo_root()
    
    try:
        result = tool_rag_search(query, repo_root=repo_root, limit=limit)
        
        if json_output:
            # Format as JSON
            payload = {
                "query": query,
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
                            }
                        }
                    }
                    for it in result.items
                ]
            }
            typer.echo(json.dumps(payload, indent=2))
        else:
            # Text output
            for i, it in enumerate(result.items, 1):
                loc = it.snippet.location
                typer.echo(f"{i}. {loc.path}:{loc.start_line}-{loc.end_line}")
                typer.echo(f"   {it.snippet.text[:100]}...")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


def nav_where_used(
    symbol: str,
    limit: int = typer.Option(10, help="Max results"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output"),
):
    """Find where a symbol is used (callers, importers)."""
    from tools.rag import tool_where_used
    
    repo_root = find_repo_root()
    
    try:
        result = tool_where_used(symbol, repo_root=repo_root, limit=limit)
        
        if json_output:
            typer.echo(json.dumps(result, indent=2, default=str))
        else:
            typer.echo(f"Where-used results for '{symbol}':")
            for i, item in enumerate(result.get("items", []), 1):
                typer.echo(f"{i}. {item}")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


def nav_lineage(
    symbol: str,
    depth: int = typer.Option(2, help="Max depth to traverse"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output"),
):
    """Show symbol lineage (parents, children, dependencies)."""
    from tools.rag import tool_lineage
    
    repo_root = find_repo_root()
    
    try:
        result = tool_lineage(symbol, repo_root=repo_root, depth=depth)
        
        if json_output:
            typer.echo(json.dumps(result, indent=2, default=str))
        else:
            typer.echo(f"Lineage for '{symbol}':")
            for i, item in enumerate(result.get("items", []), 1):
                typer.echo(f"{i}. {item}")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)