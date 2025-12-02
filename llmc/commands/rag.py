import typer
from typing import Optional, List
from pathlib import Path
import json
import sys

# Imports from existing tools
from tools.rag.indexer import index_repo as run_index_repo
from tools.rag.search import search_spans as run_search_spans
from tools.rag.inspector import inspect_entity as run_inspect_entity
from tools.rag.planner import generate_plan as run_generate_plan
from tools.rag.doctor import run_rag_doctor as run_doctor
from tools.rag.database import Database
from tools.rag.config import index_path_for_read, get_est_tokens_per_span
from llmc.core import find_repo_root

def index(
    since: Optional[str] = typer.Option(None, help="Only parse files changed since the given commit"),
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
    symbol: Optional[str] = typer.Option(None, "--symbol", "-s", help="Symbol to inspect"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="File path"),
    line: Optional[int] = typer.Option(None, "--line", "-l", help="Line number"),
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