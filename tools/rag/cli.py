from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable, List, Optional

import click

from .database import Database
from .planner import generate_plan, plan_as_dict
from .workers import (
    default_enrichment_callable,
    embedding_plan,
    enrichment_plan,
    execute_embeddings,
    execute_enrichment,
)

EST_TOKENS_PER_SPAN = 350  # heuristic for remote LLM tokens we avoid per indexed span

_RAG_DIR = ".rag"
_INDEX_DB = "index.db"
_SPANS_JSON = "spans.jsonl"


def _db_path(repo_root: Path) -> Path:
    return repo_root / _RAG_DIR / _INDEX_DB


def _repo_paths(repo_root: Path) -> Path:
    return repo_root / _RAG_DIR


def _spans_export_path(repo_root: Path) -> Path:
    return repo_root / _RAG_DIR / _SPANS_JSON


def _find_repo_root(start: Optional[Path] = None) -> Path:
    start = start or Path.cwd()
    current = start.resolve()
    for ancestor in [current, *current.parents]:
        if (ancestor / ".git").exists():
            return ancestor
    return current


@click.group()
@click.version_option("0.1.0")
def cli() -> None:
    """RAG ingestion CLI"""


@cli.command()
@click.option("--since", metavar="SHA", help="Only parse files changed since the given commit")
@click.option("--no-export", is_flag=True, default=False, help="Skip JSONL span export")
def index(since: Optional[str], no_export: bool) -> None:
    """Index the repository (full or incremental)."""
    from .indexer import index_repo

    stats = index_repo(since=since, export_json=not no_export)
    click.echo(
        f"Indexed {stats['files']} files, {stats['spans']} spans in {stats['duration_sec']}s (skipped={stats.get('skipped',0)})"
    )


def _collect_paths(paths: Iterable[str], use_stdin: bool) -> List[Path]:
    collected: List[Path] = []
    if paths:
        collected.extend(Path(p) for p in paths)
    if use_stdin:
        for line in sys.stdin:
            line = line.strip()
            if line:
                collected.append(Path(line))
    return collected


@cli.command()
@click.option("--path", "paths", multiple=True, type=click.Path(), help="Specific file or directory paths to sync")
@click.option("--since", metavar="SHA", help="Sync files changed since commit")
@click.option("--stdin", "use_stdin", is_flag=True, default=False, help="Read newline-delimited paths from stdin")
def sync(paths: Iterable[str], since: Optional[str], use_stdin: bool) -> None:
    """Incrementally update spans for selected files."""
    from .indexer import sync_paths
    from .utils import git_changed_paths

    repo_root = _find_repo_root()
    path_list: List[Path]
    if since:
        path_list = git_changed_paths(repo_root, since)
    else:
        path_list = _collect_paths(paths, use_stdin)

    if not path_list:
        click.echo("No paths to sync.")
        return

    stats = sync_paths(path_list)
    click.echo(
        f"Synced {stats['files']} files, {stats['spans']} spans, deleted={stats.get('deleted',0)} in {stats['duration_sec']}s"
    )


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Emit stats as JSON.")
def stats(as_json: bool) -> None:
    """Print summary stats for the current index."""
    repo_root = _find_repo_root()
    db_file = _db_path(repo_root)
    if not db_file.exists():
        click.echo("No index database found. Run `rag index` first.")
        return
    db = Database(db_file)
    try:
        info = db.stats()
    finally:
        db.close()
    estimated_remote_tokens = info["spans"] * EST_TOKENS_PER_SPAN
    data = {
        **info,
        "estimated_remote_tokens": estimated_remote_tokens,
        "estimated_token_savings": estimated_remote_tokens,
        "token_savings_basis": f"{EST_TOKENS_PER_SPAN} tokens per span heuristic",
    }
    if as_json:
        click.echo(json.dumps(data, indent=2))
    else:
        click.echo(
            "Files: {files}\nSpans: {spans}\nEmbeddings: {embeddings}\nEnrichments: {enrichments}\nEstimated remote tokens avoided: {estimated_remote_tokens} ({estimated_remote_tokens_k:.2f}K tokens)".format(
                estimated_remote_tokens_k=estimated_remote_tokens / 1000, **data
            )
        )


@cli.command()
def paths() -> None:
    """Show index storage paths."""
    repo_root = _find_repo_root()
    click.echo(f"RAG dir: {_repo_paths(repo_root)}")
    click.echo(f"Database: {_db_path(repo_root)}")
    click.echo(f"Spans JSONL: {_spans_export_path(repo_root)}")


@cli.command()
@click.option("--limit", default=10, show_default=True, help="Maximum spans to include in the plan.")
@click.option("--dry-run/--execute", default=True, show_default=True, help="Preview work items instead of running the LLM.")
@click.option("--model", default="local-qwen", show_default=True, help="Model identifier to record with enrichment results.")
@click.option("--cooldown", default=0, show_default=True, type=int, help="Skip spans whose files changed within the last N seconds.")
def enrich(limit: int, dry_run: bool, model: str, cooldown: int) -> None:
    """Preview or execute enrichment tasks (summary/tags) for spans."""
    repo_root = _find_repo_root()
    db_file = _db_path(repo_root)
    if not db_file.exists():
        click.echo("No index database found. Run `rag index` first.")
        return
    db = Database(db_file)
    try:
        if dry_run:
            plan = enrichment_plan(db, repo_root, limit=limit, cooldown_seconds=cooldown)
            if not plan:
                click.echo("No spans pending enrichment.")
                return
            click.echo(json.dumps(plan, indent=2, ensure_ascii=False))
            click.echo("\n(Dry run only. Pass --execute to persist enrichment results.)")
            return

        llm = default_enrichment_callable(model)
        successes, errors = execute_enrichment(db, repo_root, llm, limit=limit, model=model, cooldown_seconds=cooldown)
    finally:
        db.close()

    if successes:
        click.echo(f"Stored enrichment metadata for {successes} spans using {model}.")
    else:
        click.echo("No spans enriched.")
    if errors:
        for err in errors:
            click.echo(f"ERROR: {err}", err=True)
        raise SystemExit(1)


@cli.command()
@click.option("--limit", default=10, show_default=True, help="Maximum spans to include in the plan.")
@click.option("--dry-run/--execute", default=True, show_default=True, help="Preview work items instead of generating embeddings.")
@click.option("--model", default="hash-emb-v1", show_default=True, help="Embedding model identifier to record.")
@click.option("--dim", default=64, show_default=True, type=int, help="Embedding vector dimension.")
def embed(limit: int, dry_run: bool, model: str, dim: int) -> None:
    """Preview or execute embedding jobs for spans."""
    repo_root = _find_repo_root()
    db_file = _db_path(repo_root)
    if not db_file.exists():
        click.echo("No index database found. Run `rag index` first.")
        return
    db = Database(db_file)
    try:
        if dry_run:
            plan = embedding_plan(db, repo_root, limit=limit, model=model, dim=dim)
            if not plan:
                click.echo("No spans pending embedding.")
                return
            click.echo(json.dumps(plan, indent=2, ensure_ascii=False))
            click.echo("\n(Dry run only. Pass --execute to persist embeddings.)")
            return
        results = execute_embeddings(db, repo_root, limit=limit, model=model, dim=dim)
    finally:
        db.close()
    if not results:
        click.echo("No spans pending embedding.")
    else:
        click.echo(f"Stored embeddings for {len(results)} spans using {model} (dim={dim}).")


@cli.command()
@click.argument("query", nargs=-1)
@click.option("--limit", default=5, show_default=True, help="Maximum spans to return.")
@click.option("--min-score", default=0.4, show_default=True, help="Minimum span score to keep.")
@click.option(
    "--min-confidence",
    default=0.6,
    show_default=True,
    help="Threshold for recommending fallback to broader retrieval.",
)
@click.option(
    "--no-log",
    is_flag=True,
    default=False,
    help="Skip appending planner metrics to logs/planner_metrics.jsonl.",
)
def plan(query: List[str], limit: int, min_score: float, min_confidence: float, no_log: bool) -> None:
    """Generate a heuristic retrieval plan for a natural language query."""
    question = " ".join(query).strip()
    if not question:
        click.echo("Provide a query, e.g. `rag plan \"Where do we validate JWTs?\"`")
        raise SystemExit(1)

    repo_root = _find_repo_root()
    db_file = _db_path(repo_root)
    if not db_file.exists():
        click.echo("No index database found. Run `rag index` first.")
        return

    result = generate_plan(
        question,
        limit=limit,
        min_score=min_score,
        min_confidence=min_confidence,
        repo_root=repo_root,
        log=not no_log,
    )
    click.echo(json.dumps(plan_as_dict(result), indent=2, ensure_ascii=False))
    if result.fallback_recommended:
        click.echo("\n⚠️  Confidence below threshold; include additional context or full-text search.", err=True)


if __name__ == "__main__":
    cli()
