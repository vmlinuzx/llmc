from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
import sys
import time

import click

from .benchmark import run_embedding_benchmark
from .config import (
    get_est_tokens_per_span,
    index_path_for_read,
    index_path_for_write,
    rag_dir,
    spans_export_path as resolve_spans_export_path,
)
from .database import Database
from .planner import generate_plan, plan_as_dict
from .schema import build_graph_for_repo as schema_build_graph_for_repo
from .search import search_spans
from .workers import (
    default_enrichment_callable,
    embedding_plan,
    enrichment_plan,
    execute_embeddings,
    execute_enrichment,
)


def _db_path(repo_root: Path, *, for_write: bool) -> Path:
    if for_write:
        return index_path_for_write(repo_root)
    return index_path_for_read(repo_root)


def _repo_paths(repo_root: Path) -> Path:
    return rag_dir(repo_root)


def _spans_export_path(repo_root: Path) -> Path:
    return resolve_spans_export_path(repo_root)


def _find_repo_root(start: Path | None = None) -> Path:
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
@click.option(
    "--since", metavar="SHA", help="Only parse files changed since the given commit"
)
@click.option("--no-export", is_flag=True, default=False, help="Skip JSONL span export")
@click.option("--json", "as_json", is_flag=True, help="Emit output as JSON.")
@click.option(
    "--show-domain-decisions", is_flag=True, help="Show domain resolution decisions."
)
def index(
    since: str | None, no_export: bool, as_json: bool, show_domain_decisions: bool
) -> None:
    """Index the repository (full or incremental)."""
    from .indexer import index_repo

    stats = index_repo(
        since=since,
        export_json=not no_export,
        show_domain_decisions=show_domain_decisions,
    )
    if as_json:
        click.echo(json.dumps(stats, indent=2))
    else:
        click.echo(
            f"Indexed {stats['files']} files, {stats['spans']} spans in {stats['duration_sec']}s "
            f"(skipped={stats.get('skipped', 0)}, unchanged={stats.get('unchanged', 0)})"
        )


def _collect_paths(paths: Iterable[str], use_stdin: bool) -> list[Path]:
    collected: list[Path] = []
    if paths:
        collected.extend(Path(p) for p in paths)
    if use_stdin:
        for raw_line in sys.stdin:
            line = raw_line.strip()
            if line:
                collected.append(Path(line))
    return collected


@cli.command()
@click.option(
    "--path",
    "paths",
    multiple=True,
    type=click.Path(),
    help="Specific file or directory paths to sync",
)
@click.option("--since", metavar="SHA", help="Sync files changed since commit")
@click.option(
    "--stdin",
    "use_stdin",
    is_flag=True,
    default=False,
    help="Read newline-delimited paths from stdin",
)
@click.option("--json", "as_json", is_flag=True, help="Emit output as JSON.")
def sync(
    paths: Iterable[str], since: str | None, use_stdin: bool, as_json: bool
) -> None:
    """Incrementally update spans for selected files."""
    from .indexer import sync_paths
    from .utils import git_changed_paths

    repo_root = _find_repo_root()
    path_list: list[Path]
    if since:
        path_list = git_changed_paths(repo_root, since)
    else:
        path_list = _collect_paths(paths, use_stdin)

    if not path_list:
        if as_json:
            click.echo(json.dumps({"error": "No paths to sync"}, indent=2))
        else:
            click.echo("No paths to sync.")
        return

    stats = sync_paths(path_list)
    if as_json:
        click.echo(json.dumps(stats, indent=2))
    else:
        click.echo(
            f"Synced {stats['files']} files, {stats['spans']} spans, "
            f"deleted={stats.get('deleted', 0)}, unchanged={stats.get('unchanged', 0)} in {stats['duration_sec']}s"
        )


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Emit stats as JSON.")
def stats(as_json: bool) -> None:
    """Print summary stats for the current index."""
    repo_root = _find_repo_root()
    db_file = _db_path(repo_root, for_write=False)
    if not db_file.exists():
        click.echo("No index database found. Run `rag index` first.")
        return
    db = Database(db_file)
    try:
        info = db.stats()
    finally:
        db.close()
    est_tokens = get_est_tokens_per_span(repo_root)
    estimated_remote_tokens = info["spans"] * est_tokens
    data = {
        **info,
        "estimated_remote_tokens": estimated_remote_tokens,
        "estimated_token_savings": estimated_remote_tokens,
        "token_savings_basis": f"{est_tokens} tokens per span heuristic",
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
    click.echo(f"Database: {_db_path(repo_root, for_write=False)}")
    click.echo(f"Spans JSONL: {_spans_export_path(repo_root)}")


@cli.command()
@click.option(
    "--require-enrichment/--allow-empty-enrichment",
    default=True,
    show_default=True,
    help=(
        "Require enrichment data in the index database. When disabled, "
        "build a plain AST-only schema graph without enforcing enrichment coverage."
    ),
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Optional path to write the graph JSON (default: .llmc/rag_graph.json).",
)
def graph(require_enrichment: bool, output_path: Path | None) -> None:
    """Build a schema graph for the current repository.

    By default this will:

    - Discover Python source files under the current repo root.
    - Build a SchemaGraph (AST-only or enriched, depending on flags).
    - Write the graph JSON to .llmc/rag_graph.json.

    Use --allow-empty-enrichment to bypass enrichment gating and build
    a plain AST-only graph even when no enrichments are present.
    """
    repo_root = _find_repo_root()

    # Default output location mirrors the existing RAG Nav conventions.
    if output_path is None:
        llmc_dir = repo_root / ".llmc"
        llmc_dir.mkdir(parents=True, exist_ok=True)
        output_path = llmc_dir / "rag_graph.json"

    try:
        graph = schema_build_graph_for_repo(
            repo_root,
            require_enrichment=require_enrichment,
        )
    except RuntimeError as err:
        # Surface enrichment gating failures (e.g. zero rows or zero attached entities)
        click.echo(str(err), err=True)
        raise SystemExit(1) from err
    except FileNotFoundError as err:
        # Missing index DB or other filesystem issues
        click.echo(str(err), err=True)
        raise SystemExit(1) from err

    graph.save(output_path)
    click.echo(f"Wrote graph JSON to {output_path}")


@cli.command()
@click.option(
    "--limit",
    default=10,
    show_default=True,
    help="Maximum spans to include in the plan.",
)
@click.option(
    "--dry-run/--execute",
    default=True,
    show_default=True,
    help="Preview work items instead of running the LLM.",
)
@click.option(
    "--model",
    default="local-qwen",
    show_default=True,
    help="Model identifier to record with enrichment results.",
)
@click.option(
    "--cooldown",
    default=0,
    show_default=True,
    type=int,
    help="Skip spans whose files changed within the last N seconds.",
)
@click.option(
    "--code-first",
    is_flag=True,
    default=False,
    help="Use code-first prioritization for enrichment (overrides config).",
)
@click.option(
    "--no-code-first",
    is_flag=True,
    default=False,
    help="Disable code-first prioritization and use legacy ordering.",
)
@click.option(
    "--starvation-ratio",
    default="5:1",
    show_default=True,
    help="High:Low ratio for mixing high/low priority tasks when code-first is enabled (e.g. 5:1).",
)
def enrich(
    limit: int,
    dry_run: bool,
    model: str,
    cooldown: int,
    code_first: bool,
    no_code_first: bool,
    starvation_ratio: str,
) -> None:
    """Preview or execute enrichment tasks (summary/tags) for spans."""
    if limit < 1:
        click.echo("Limit must be at least 1.", err=True)
        raise SystemExit(1)

    repo_root = _find_repo_root()

    if code_first and no_code_first:
        click.echo(
            "Error: cannot pass both --code-first and --no-code-first.", err=True
        )
        raise SystemExit(1)

    code_first_override: bool | None
    if code_first:
        code_first_override = True
    elif no_code_first:
        code_first_override = False
    else:
        code_first_override = None

    sr_high: int | None = None
    sr_low: int | None = None
    if code_first_override is True:
        try:
            high_str, low_str = starvation_ratio.split(":", 1)
            sr_high = max(1, int(high_str))
            sr_low = max(1, int(low_str))
        except Exception:
            click.echo(
                "Error: invalid --starvation-ratio value. Expected format HIGH:LOW (e.g. 5:1).",
                err=True,
            )
            raise SystemExit(1) from None
    db_file = _db_path(repo_root, for_write=False)
    if not db_file.exists():
        click.echo("No index database found. Run `rag index` first.")
        return
    db = Database(db_file)
    try:
        if dry_run:
            plan = enrichment_plan(
                db, repo_root, limit=limit, cooldown_seconds=cooldown
            )
            if not plan:
                click.echo("No spans pending enrichment.")
                return
            click.echo(json.dumps(plan, indent=2, ensure_ascii=False))
            click.echo(
                "\n(Dry run only. Pass --execute to persist enrichment results.)"
            )
            return

        llm = default_enrichment_callable(model)
        successes, errors = execute_enrichment(
            db,
            repo_root,
            llm,
            limit=limit,
            model=model,
            cooldown_seconds=cooldown,
            code_first=code_first_override,
            starvation_ratio_high=sr_high,
            starvation_ratio_low=sr_low,
        )
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
@click.option(
    "--limit",
    default=10,
    show_default=True,
    help="Maximum spans to include in the plan.",
)
@click.option(
    "--dry-run/--execute",
    default=True,
    show_default=True,
    help="Preview work items instead of generating embeddings.",
)
@click.option(
    "--model",
    default="auto",
    show_default=True,
    help="Embedding model identifier (`auto` uses configured default).",
)
@click.option(
    "--dim",
    default=0,
    show_default=True,
    type=int,
    help="Embedding dimension (0 uses the model default).",
)
def embed(limit: int, dry_run: bool, model: str, dim: int) -> None:
    """Preview or execute embedding jobs for spans."""
    if limit < 1:
        click.echo("Limit must be at least 1.", err=True)
        raise SystemExit(1)

    repo_root = _find_repo_root()
    db_file = _db_path(repo_root, for_write=False)
    if not db_file.exists():
        click.echo("No index database found. Run `rag index` first.")
        return
    db = Database(db_file)
    try:
        model_arg = None if model == "auto" else model
        dim_arg = None if dim <= 0 else dim

        if dry_run:
            plan = embedding_plan(
                db, repo_root, limit=limit, model=model_arg, dim=dim_arg
            )
            if not plan:
                click.echo("No spans pending embedding.")
                return
            click.echo(json.dumps(plan, indent=2, ensure_ascii=False))
            click.echo("\n(Dry run only. Pass --execute to persist embeddings.)")
            return
        results, used_model, used_dim = execute_embeddings(
            db, repo_root, limit=limit, model=model_arg, dim=dim_arg
        )
    finally:
        db.close()
    if not results:
        click.echo("No spans pending embedding.")
    else:
        click.echo(
            f"Stored embeddings for {len(results)} spans using {used_model} (dim={used_dim})."
        )


@cli.command()
@click.argument("query", nargs=-1)
@click.option("--limit", default=5, show_default=True, help="Maximum spans to return.")
@click.option("--json", "as_json", is_flag=True, help="Emit results as JSON.")
@click.option(
    "--debug", is_flag=True, help="Include debug metadata (graph, enrichment, scores)."
)
def search(query: list[str], limit: int, as_json: bool, debug: bool) -> None:
    """Run a cosine-similarity search over the local embedding index."""
    phrase = " ".join(query).strip()
    if not phrase:
        click.echo('Provide a query, e.g. `rag search "How do we verify JWTs?"`')
        return
    if limit < 1:
        click.echo("Limit must be at least 1.", err=True)
        raise SystemExit(1)

    try:
        results = search_spans(phrase, limit=limit, debug=debug)
    except FileNotFoundError as err:
        click.echo(str(err))
        raise SystemExit(1) from err
    if as_json:
        payload = [
            {
                "rank": idx + 1,
                "span_hash": result.span_hash,
                "path": str(result.path),
                "symbol": result.symbol,
                "kind": result.kind,
                "lines": [result.start_line, result.end_line],
                "score": result.score,
                "normalized_score": getattr(result, "normalized_score", 0.0),
                "summary": result.summary,
                "debug": result.debug_info,
            }
            for idx, result in enumerate(results)
        ]
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    if not results:
        click.echo("No spans found.")
        return
    for idx, result in enumerate(results, 1):
        # Normalized score display: [ 95.0] (0.950)
        norm_score = getattr(result, "normalized_score", 0.0)
        click.echo(
            f"{idx}. [{norm_score:5.1f}] ({result.score:.3f}) • {result.path}:{result.start_line}-{result.end_line} • {result.symbol} ({result.kind})"
        )
        if result.summary:
            click.echo(f"    summary: {result.summary}")
        if debug and result.debug_info:
            # Minimal debug output for text mode, mostly for verification
            click.echo(
                f"    [DEBUG] Graph Node: {result.debug_info.get('graph', {}).get('node_id', 'N/A')}"
            )


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Emit metrics as JSON.")
@click.option(
    "--top1-threshold",
    default=0.75,
    show_default=True,
    type=float,
    help="Minimum top-1 accuracy required for success.",
)
@click.option(
    "--margin-threshold",
    default=0.1,
    show_default=True,
    type=float,
    help="Minimum average positive-minus-negative score margin required.",
)
def benchmark(as_json: bool, top1_threshold: float, margin_threshold: float) -> None:
    """Run a lightweight embedding quality benchmark."""
    metrics = run_embedding_benchmark()
    success = (
        metrics["top1_accuracy"] >= top1_threshold
        and metrics["avg_margin"] >= margin_threshold
    )
    report = {
        **metrics,
        "top1_threshold": top1_threshold,
        "margin_threshold": margin_threshold,
        "passed": success,
    }
    if as_json:
        click.echo(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        click.echo(
            "Embedding benchmark results:\n"
            f"  cases           : {int(report['cases'])}\n"
            f"  top1_accuracy   : {report['top1_accuracy']:.3f} (threshold {top1_threshold:.2f})\n"
            f"  avg_margin      : {report['avg_margin']:.3f} (threshold {margin_threshold:.2f})\n"
            f"  avg_positive    : {report['avg_positive_score']:.3f}\n"
            f"  avg_negative    : {report['avg_negative_score']:.3f}\n"
            f"  status          : {'PASS' if success else 'FAIL'}"
        )
    if not success:
        raise SystemExit(1)


@cli.command()
@click.argument("query", nargs=-1)
@click.option("--limit", default=5, show_default=True, help="Maximum spans to return.")
@click.option(
    "--min-score", default=0.4, show_default=True, help="Minimum span score to keep."
)
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
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Emit plan as JSON (default; kept for ergonomics).",
)
def plan(
    query: list[str],
    limit: int,
    min_score: float,
    min_confidence: float,
    no_log: bool,
    as_json: bool,
) -> None:
    """Generate a heuristic retrieval plan for a natural language query."""
    question = " ".join(query).strip()
    if not question:
        click.echo('Provide a query, e.g. `rag plan "Where do we validate JWTs?"`')
        raise SystemExit(1)
    if limit < 1:
        click.echo("Limit must be at least 1.", err=True)
        raise SystemExit(1)

    repo_root = _find_repo_root()
    db_file = _db_path(repo_root, for_write=False)
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
    # The planner already emits JSON by default; the --json flag exists for
    # compatibility and ergonomics (e.g., piping into jq).
    click.echo(json.dumps(plan_as_dict(result), indent=2, ensure_ascii=False))
    if result.fallback_recommended:
        click.echo(
            "\n⚠️  Confidence below threshold; include additional context or full-text search.",
            err=True,
        )


@cli.command()
@click.option("--json", "as_json", is_flag=True, help="Emit doctor report as JSON.")
@click.option("--verbose", "-v", is_flag=True, help="Include extra checks in output.")
def doctor(as_json: bool, verbose: bool) -> None:
    """Run RAG database health checks and diagnostics."""
    from .doctor import format_rag_doctor_summary, run_rag_doctor

    repo_root = _find_repo_root()
    result = run_rag_doctor(repo_root, verbose=verbose)

    if as_json:
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        click.echo(format_rag_doctor_summary(result, repo_root.name))
        if verbose and result.get("top_pending_files"):
            click.echo("  Top files with pending enrichments:")
            for item in result["top_pending_files"]:
                click.echo(f"    - {item['path']} ({item['pending_spans']} spans)")

    status = result.get("status", "OK")
    exit_code = 0
    if status not in ("OK", "EMPTY"):
        exit_code = 1
    sys.exit(exit_code)


@cli.command()
@click.option("--output", "-o", type=click.Path(), help="Output archive path")
def export(output: str | None) -> None:
    """Export all RAG data to tar.gz archive."""
    from .export_data import run_export

    repo_root = _find_repo_root()
    output_path = Path(output) if output else None
    run_export(repo_root=repo_root, output_path=output_path)


@cli.command()
@click.option("--path", help="File path to inspect.")
@click.option(
    "--symbol", help="Symbol name to resolve (e.g. 'tools.rag.search.search_spans')."
)
@click.option("--line", type=int, help="Line number to focus on (if path provided).")
@click.option("--full", "full_source", is_flag=True, help="Include full source code.")
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
def inspect(
    path: str | None,
    symbol: str | None,
    line: int | None,
    full_source: bool,
    as_json: bool,
) -> None:
    """Fast inspection of a file or symbol with graph + enrichment context.

    Does NOT load embedding models.
    """
    from .inspector import inspect_entity

    if not path and not symbol:
        click.echo("Error: Must provide either --path or --symbol", err=True)
        raise SystemExit(1)

    repo_root = _find_repo_root()

    try:
        result = inspect_entity(
            repo_root,
            path=path,
            symbol=symbol,
            line=line,
            include_full_source=full_source,
        )
    except Exception as e:
        click.echo(f"Error inspecting entity: {e}", err=True)
        raise SystemExit(1) from e

    if as_json:
        click.echo(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    # Text Output
    click.echo(f"# FILE: {result.path}")
    click.echo(f"# SOURCE_MODE: {result.source_mode}")
    if symbol:
        click.echo(f"# SYMBOL: {symbol}")

    prov_kind = result.provenance.get("kind", "unknown")
    click.echo(f"# KIND: {prov_kind}")

    summary = result.file_summary or result.enrichment.get("summary")
    if summary:
        click.echo(f"# SUMMARY: {summary}")

    if result.defined_symbols:
        click.echo("# DEFINED SYMBOLS:")
        for sym in result.defined_symbols[:10]:
            click.echo(f"#   - {sym.name} ({sym.type}, line {sym.line})")

    click.echo("# RELATIONSHIPS:")

    def print_rels(label, items):
        if items:
            vals = ", ".join(i.symbol or i.path for i in items)
            click.echo(f"#   - {label}: {vals}")

    print_rels("Parents", result.parents)
    print_rels("Children", result.children)
    print_rels("Calls", result.outgoing_calls)
    print_rels("Called by", result.incoming_calls)
    print_rels("Tests", result.related_tests)
    print_rels("Docs", result.related_docs)

    # Check if graph seems empty/disconnected for this file
    has_rels = any(
        [
            result.parents,
            result.children,
            result.outgoing_calls,
            result.incoming_calls,
            result.related_tests,
            result.related_docs,
        ]
    )
    if not has_rels:
        status = result.graph_status
        if status == "graph_missing":
            click.echo("# GRAPH STATUS: ⚠️  Graph not found. Run 'rag graph' to build.")
        elif status == "file_not_indexed":
            click.echo("# GRAPH STATUS: ⚠️  File not found in graph index.")
        elif status == "isolated":
            click.echo(
                "# GRAPH STATUS: ⚠️  File indexed but isolated (no relationships found)."
            )

    click.echo("")
    if result.primary_span:
        click.echo(
            f"# SNIPPET (lines {result.primary_span[0]}-{result.primary_span[1]}):"
        )
    else:
        click.echo("# SNIPPET:")

    if full_source and result.full_source:
        click.echo(result.full_source)
    else:
        click.echo(result.snippet)


@cli.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path (default: stdout).",
)
@click.option(
    "--limit",
    default=500,
    show_default=True,
    help="Maximum files to include.",
)
def skeleton(output: Path | None, limit: int) -> None:
    """Generate a minimalist repository skeleton for LLM context."""
    from .skeleton import generate_repo_skeleton
    
    repo_root = _find_repo_root()
    skeleton_text = generate_repo_skeleton(repo_root, max_files=limit)
    
    if output:
        output.write_text(skeleton_text, encoding="utf-8")
        click.echo(f"Wrote skeleton to {output}")
    else:
        click.echo(skeleton_text)


@cli.group(
    help="Navigation tools over graph/fallback with freshness metadata.",
    invoke_without_command=True,
)
@click.option(
    "--print-schema",
    "print_schema",
    is_flag=True,
    help="Print schema manifest JSON and exit.",
)
@click.pass_context
def nav(ctx: click.Context, print_schema: bool) -> None:
    """RAG Nav helpers (search/where-used/lineage)."""
    if print_schema:
        repo_root = _find_repo_root()
        _emit_schema_manifest(repo_root)
        return
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@nav.command()
@click.argument("symbol")
def read(symbol: str) -> None:
    """Read the implementation code for a specific symbol."""
    from .reader import read_implementation
    
    repo_root = _find_repo_root()
    span = read_implementation(repo_root, symbol)
    
    if span:
        click.echo(f"## Impl: {span.symbol}")
        click.echo(f"# Location: {span.file_path}:{span.start_line}-{span.end_line}")
        click.echo("```python")
        click.echo(span.content)
        click.echo("```")
    else:
        click.echo(f"Symbol '{symbol}' not found in graph.", err=True)




def _route_to_dict(repo_root: Path) -> dict:
    """Compute Context Gateway route and return a JSON-serializable dict."""
    from dataclasses import asdict, is_dataclass

    from llmc.rag_nav.gateway import compute_route

    route = compute_route(repo_root)
    status = getattr(route, "status", None)
    if status is not None:
        try:
            if is_dataclass(status):
                status_dict = asdict(status)
            else:
                fields = [
                    "index_state",
                    "last_indexed_commit",
                    "last_indexed_at",
                    "schema_version",
                    "last_error",
                ]
                status_dict = {k: getattr(status, k, None) for k in fields}
        except Exception:
            status_dict = None
    else:
        status_dict = None

    return {
        "use_rag": getattr(route, "use_rag", False),
        "freshness_state": getattr(route, "freshness_state", "UNKNOWN"),
        "status": status_dict,
    }


def _preview_line(text: str, width: int) -> str:
    """Collapse whitespace and truncate to width."""
    import re as _re

    s = _re.sub(r"\s+", " ", (text or "").strip())
    if len(s) > width:
        return s[: max(0, width - 1)] + "…"
    return s


def _colorize_header(route_info: dict, items_len: int, use_color: bool) -> str:
    import click as _click

    route_name = "RAG_GRAPH" if route_info.get("use_rag") else "LOCAL_FALLBACK"
    fresh = (route_info.get("freshness_state") or "UNKNOWN").upper()
    if not use_color:
        return f"[route={route_name}] [freshness={fresh}] [items={items_len}]"
    color_map = {"FRESH": "green", "STALE": "yellow", "UNKNOWN": "blue"}
    cf = color_map.get(fresh, "blue")
    return " ".join(
        [
            _click.style(f"[route={route_name}]", fg="cyan"),
            _click.style(f"[freshness={fresh}]", fg=cf),
            _click.style(f"[items={items_len}]", fg="white"),
        ]
    )


def _emit_jsonl_line(obj: dict) -> None:
    import json as _json

    import click as _click

    _click.echo(_json.dumps(obj, ensure_ascii=False))


def _now_iso() -> str:
    import datetime as _dt

    # Use timezone-aware UTC timestamp to avoid deprecated utcnow.
    return (
        _dt.datetime.now(_dt.UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _emit_start_event(command: str, **kw) -> None:
    payload = {"type": "start", "command": command, "ts": _now_iso()}
    payload.update({k: v for k, v in kw.items() if v is not None})
    _emit_jsonl_line(payload)


def _emit_end_event(command: str, total: int, elapsed_ms: int) -> None:
    _emit_jsonl_line(
        {
            "type": "end",
            "command": command,
            "total": total,
            "elapsed_ms": elapsed_ms,
            "ts": _now_iso(),
        }
    )


def _emit_error_event(command: str, message: str, code: str | None = None) -> None:
    evt: dict = {
        "type": "error",
        "command": command,
        "message": message,
        "ts": _now_iso(),
    }
    if code:
        evt["code"] = code
    _emit_jsonl_line(evt)


def _schema_paths(repo_root: Path) -> dict:
    base = repo_root / "DOCS" / "RAG_NAV" / "SCHEMAS" / "schemas"
    return {
        "route": base / "route.schema.json",
        "location": base / "location.schema.json",
        "snippet": base / "snippet.schema.json",
        "item": base / "item.schema.json",
        "search": base / "search_result.schema.json",
        "where_used": base / "where_used_result.schema.json",
        "lineage": base / "lineage_result.schema.json",
        "jsonl_event": base / "jsonl_event.schema.json",
    }


def _read_json_file(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _emit_schema_manifest(repo_root: Path) -> None:
    paths = _schema_paths(repo_root)
    schemas_inline = {name: _read_json_file(p) for name, p in paths.items()}
    manifest = {
        "name": "llmc.rag_nav",
        "version": "1.0.0",
        "commands": [
            {
                "cmd": "nav search",
                "json": {"schema": "llmc://schemas/rag_nav/search_result.schema.json"},
                "jsonl": {"schema": "llmc://schemas/rag_nav/jsonl_event.schema.json"},
            },
            {
                "cmd": "nav where-used",
                "json": {
                    "schema": "llmc://schemas/rag_nav/where_used_result.schema.json"
                },
                "jsonl": {"schema": "llmc://schemas/rag_nav/jsonl_event.schema.json"},
            },
            {
                "cmd": "nav lineage",
                "json": {"schema": "llmc://schemas/rag_nav/lineage_result.schema.json"},
                "jsonl": {"schema": "llmc://schemas/rag_nav/jsonl_event.schema.json"},
            },
        ],
        "schemas": {
            "route": "llmc://schemas/rag_nav/route.schema.json",
            "location": "llmc://schemas/rag_nav/location.schema.json",
            "snippet": "llmc://schemas/rag_nav/snippet.schema.json",
            "item": "llmc://schemas/rag_nav/item.schema.json",
            "search": "llmc://schemas/rag_nav/search_result.schema.json",
            "where_used": "llmc://schemas/rag_nav/where_used_result.schema.json",
            "lineage": "llmc://schemas/rag_nav/lineage_result.schema.json",
            "jsonl_event": "llmc://schemas/rag_nav/jsonl_event.schema.json",
        },
        "schemas_inline": schemas_inline,
        "docs_paths": {name: str(p) for name, p in paths.items()},
    }
    click.echo(json.dumps(manifest, indent=2, ensure_ascii=False))


@nav.command("print-schema")
def nav_print_schema() -> None:
    """Print schema manifest JSON and exit (alias for --print-schema)."""
    repo_root = _find_repo_root()
    _emit_schema_manifest(repo_root)


@nav.command("search")
@click.argument("query", nargs=-1)
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Repository root (defaults to auto-detected).",
)
@click.option(
    "--limit", "-n", default=10, show_default=True, help="Max results to return."
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON output.")
@click.option(
    "--jsonl",
    "as_jsonl",
    is_flag=True,
    help="Emit JSON Lines (JSONL) output, one object per line.",
)
@click.option(
    "--jsonl-compact",
    "as_jsonl_compact",
    is_flag=True,
    help="Emit compact JSONL items without snippet text.",
)
@click.option(
    "--preview/--no-preview",
    default=True,
    show_default=True,
    help="Show first-line preview of the snippet in text mode.",
)
@click.option(
    "--width",
    "-w",
    default=96,
    show_default=True,
    help="Max preview width in characters.",
)
@click.option(
    "--color/--no-color", default=True, show_default=True, help="Colorize text output."
)
def nav_search(
    query: list[str],
    repo: str | None,
    limit: int,
    as_json: bool,
    as_jsonl: bool,
    as_jsonl_compact: bool,
    preview: bool,
    width: int,
    color: bool,
) -> None:
    """Semantic/structural search using graph when fresh, else local fallback."""
    if limit < 1:
        click.echo("Limit must be at least 1.", err=True)
        raise SystemExit(1)

    from llmc.rag import tool_rag_search

    phrase = " ".join(query).strip()
    if not phrase:
        click.echo('Provide a query, e.g. `rag nav search "jwt verify"`')
        raise SystemExit(2)

    if as_json and (as_jsonl or as_jsonl_compact):
        click.echo("Choose either --json or --jsonl/--jsonl-compact, not both.")
        raise SystemExit(2)

    repo_root = Path(repo) if repo else _find_repo_root()
    route_info = _route_to_dict(repo_root)

    t0 = time.perf_counter()
    try:
        if as_jsonl or as_jsonl_compact:
            _emit_start_event("search", query=phrase)
            _emit_jsonl_line({"type": "route", "route": route_info})
        result = tool_rag_search(phrase, repo_root=repo_root, limit=limit)
    except Exception as exc:
        if as_jsonl or as_jsonl_compact:
            _emit_error_event("search", f"{exc.__class__.__name__}: {exc}")
        raise

    if as_json:
        payload = {
            "query": phrase,
            "route": route_info,
            "result": {
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
            },
        }
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if as_jsonl or as_jsonl_compact:
        total = 0
        for it in result.items:
            total += 1
            if as_jsonl_compact:
                loc = it.snippet.location
                _emit_jsonl_line(
                    {
                        "type": "item",
                        "file": it.file,
                        "path": loc.path,
                        "start_line": loc.start_line,
                        "end_line": loc.end_line,
                        "source": getattr(result, "source", "UNKNOWN"),
                        "freshness_state": getattr(
                            result, "freshness_state", "UNKNOWN"
                        ),
                    }
                )
            else:
                _emit_jsonl_line(
                    {
                        "type": "item",
                        "file": it.file,
                        "snippet": {
                            "text": it.snippet.text,
                            "location": {
                                "path": it.snippet.location.path,
                                "start_line": it.snippet.location.start_line,
                                "end_line": it.snippet.location.end_line,
                            },
                        },
                        "source": getattr(result, "source", "UNKNOWN"),
                        "freshness_state": getattr(
                            result, "freshness_state", "UNKNOWN"
                        ),
                    }
                )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        _emit_end_event("search", total=total, elapsed_ms=elapsed_ms)
        return

    # pretty text mode
    click.echo(_colorize_header(route_info, len(result.items), color))
    for i, it in enumerate(result.items, start=1):
        loc = it.snippet.location
        line = f"{i:2d}. {it.file}:{loc.start_line}-{loc.end_line}"
        if preview and it.snippet and it.snippet.text:
            first_line = (
                it.snippet.text.splitlines()[0] if it.snippet.text.splitlines() else ""
            )
            line += f" — {_preview_line(first_line, width)}"
        if color:
            line = click.style(line, fg="white")
        click.echo(line)
    if not result.items:
        click.echo(
            click.style("(no results)", fg="bright_black") if color else "(no results)"
        )


@nav.command("where-used")
@click.argument("symbol")
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Repository root (defaults to auto-detected).",
)
@click.option(
    "--limit", "-n", default=50, show_default=True, help="Max results to return."
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON output.")
@click.option(
    "--jsonl",
    "as_jsonl",
    is_flag=True,
    help="Emit JSON Lines (JSONL) output, one object per line.",
)
@click.option(
    "--jsonl-compact",
    "as_jsonl_compact",
    is_flag=True,
    help="Emit compact JSONL items without snippet text.",
)
@click.option(
    "--preview/--no-preview",
    default=True,
    show_default=True,
    help="Show first-line preview of the snippet in text mode.",
)
@click.option(
    "--width",
    "-w",
    default=96,
    show_default=True,
    help="Max preview width in characters.",
)
@click.option(
    "--color/--no-color", default=True, show_default=True, help="Colorize text output."
)
def nav_where_used(
    symbol: str,
    repo: str | None,
    limit: int,
    as_json: bool,
    as_jsonl: bool,
    as_jsonl_compact: bool,
    preview: bool,
    width: int,
    color: bool,
) -> None:
    """Find usage sites of a symbol via graph edges or fallback grep."""
    if limit < 1:
        click.echo("Limit must be at least 1.", err=True)
        raise SystemExit(1)

    from llmc.rag import tool_rag_where_used

    if as_json and (as_jsonl or as_jsonl_compact):
        click.echo("Choose either --json or --jsonl/--jsonl-compact, not both.")
        raise SystemExit(2)

    repo_root = Path(repo) if repo else _find_repo_root()
    route_info = _route_to_dict(repo_root)
    t0 = time.perf_counter()

    try:
        if as_jsonl or as_jsonl_compact:
            _emit_start_event("where-used", symbol=symbol)
            _emit_jsonl_line({"type": "route", "route": route_info})
        result = tool_rag_where_used(symbol, repo_root=repo_root, limit=limit)
    except Exception as exc:
        if as_jsonl or as_jsonl_compact:
            _emit_error_event("where-used", f"{exc.__class__.__name__}: {exc}")
        raise

    if as_json:
        payload = {
            "symbol": symbol,
            "route": route_info,
            "result": {
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
            },
        }
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if as_jsonl or as_jsonl_compact:
        total = 0
        for it in result.items:
            total += 1
            if as_jsonl_compact:
                loc = it.snippet.location
                _emit_jsonl_line(
                    {
                        "type": "item",
                        "file": it.file,
                        "path": loc.path,
                        "start_line": loc.start_line,
                        "end_line": loc.end_line,
                        "source": getattr(result, "source", "UNKNOWN"),
                        "freshness_state": getattr(
                            result, "freshness_state", "UNKNOWN"
                        ),
                    }
                )
            else:
                _emit_jsonl_line(
                    {
                        "type": "item",
                        "file": it.file,
                        "snippet": {
                            "text": it.snippet.text,
                            "location": {
                                "path": it.snippet.location.path,
                                "start_line": it.snippet.location.start_line,
                                "end_line": it.snippet.location.end_line,
                            },
                        },
                        "source": getattr(result, "source", "UNKNOWN"),
                        "freshness_state": getattr(
                            result, "freshness_state", "UNKNOWN"
                        ),
                    }
                )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        _emit_end_event("where-used", total=total, elapsed_ms=elapsed_ms)
        return

    click.echo(_colorize_header(route_info, len(result.items), color))
    for i, it in enumerate(result.items, start=1):
        loc = it.snippet.location
        line = f"{i:2d}. {it.file}:{loc.start_line}-{loc.end_line}"
        if preview and it.snippet and it.snippet.text:
            first_line = (
                it.snippet.text.splitlines()[0] if it.snippet.text.splitlines() else ""
            )
            line += f" — {_preview_line(first_line, width)}"
        click.echo(click.style(line, fg="white") if color else line)
    if not result.items:
        click.echo(
            click.style("(no results)", fg="bright_black") if color else "(no results)"
        )


@nav.command("lineage")
@click.argument("symbol")
@click.option(
    "--direction",
    "-d",
    type=click.Choice(["upstream", "downstream"], case_sensitive=False),
    default="downstream",
    show_default=True,
)
@click.option(
    "--repo",
    "-r",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Repository root (defaults to auto-detected).",
)
@click.option(
    "--max-results",
    "-n",
    default=50,
    show_default=True,
    help="Max lineage hops to return.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON output.")
@click.option(
    "--jsonl",
    "as_jsonl",
    is_flag=True,
    help="Emit JSON Lines (JSONL) output, one object per line.",
)
@click.option(
    "--jsonl-compact",
    "as_jsonl_compact",
    is_flag=True,
    help="Emit compact JSONL items without snippet text.",
)
@click.option(
    "--preview/--no-preview",
    default=True,
    show_default=True,
    help="Show first-line preview of the snippet in text mode.",
)
@click.option(
    "--width",
    "-w",
    default=96,
    show_default=True,
    help="Max preview width in characters.",
)
@click.option(
    "--color/--no-color", default=True, show_default=True, help="Colorize text output."
)
def nav_lineage(
    symbol: str,
    direction: str,
    repo: str | None,
    max_results: int,
    as_json: bool,
    as_jsonl: bool,
    as_jsonl_compact: bool,
    preview: bool,
    width: int,
    color: bool,
) -> None:
    """One-hop lineage over CALLS edges (downstream=callees, upstream=callers) or fallback callsite grep."""
    if max_results < 1:
        click.echo("Limit must be at least 1.", err=True)
        raise SystemExit(1)

    from llmc.rag import tool_rag_lineage

    if as_json and (as_jsonl or as_jsonl_compact):
        click.echo("Choose either --json or --jsonl/--jsonl-compact, not both.")
        raise SystemExit(2)

    repo_root = Path(repo) if repo else _find_repo_root()
    route_info = _route_to_dict(repo_root)
    t0 = time.perf_counter()

    try:
        if as_jsonl or as_jsonl_compact:
            _emit_start_event("lineage", symbol=symbol, direction=direction)
            _emit_jsonl_line({"type": "route", "route": route_info})
        result = tool_rag_lineage(
            symbol, direction=direction, repo_root=repo_root, max_results=max_results
        )
    except Exception as exc:
        if as_jsonl or as_jsonl_compact:
            _emit_error_event("lineage", f"{exc.__class__.__name__}: {exc}")
        raise

    if as_json:
        payload = {
            "symbol": symbol,
            "direction": direction,
            "route": route_info,
            "result": {
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
            },
        }
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if as_jsonl or as_jsonl_compact:
        total = 0
        for it in result.items:
            total += 1
            if as_jsonl_compact:
                loc = it.snippet.location
                _emit_jsonl_line(
                    {
                        "type": "item",
                        "file": it.file,
                        "path": loc.path,
                        "start_line": loc.start_line,
                        "end_line": loc.end_line,
                        "source": getattr(result, "source", "UNKNOWN"),
                        "freshness_state": getattr(
                            result, "freshness_state", "UNKNOWN"
                        ),
                    }
                )
            else:
                _emit_jsonl_line(
                    {
                        "type": "item",
                        "file": it.file,
                        "snippet": {
                            "text": it.snippet.text,
                            "location": {
                                "path": it.snippet.location.path,
                                "start_line": it.snippet.location.start_line,
                                "end_line": it.snippet.location.end_line,
                            },
                        },
                        "source": getattr(result, "source", "UNKNOWN"),
                        "freshness_state": getattr(
                            result, "freshness_state", "UNKNOWN"
                        ),
                    }
                )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        _emit_end_event("lineage", total=total, elapsed_ms=elapsed_ms)
        return

    click.echo(_colorize_header(route_info, len(result.items), color))
    for i, it in enumerate(result.items, start=1):
        loc = it.snippet.location
        line = f"{i:2d}. {it.file}:{loc.start_line}-{loc.end_line}"
        if preview and it.snippet and it.snippet.text:
            first_line = (
                it.snippet.text.splitlines()[0] if it.snippet.text.splitlines() else ""
            )
            line += f" — {_preview_line(first_line, width)}"
        click.echo(click.style(line, fg="white") if color else line)
    if not result.items:
        click.echo(
            click.style("(no results)", fg="bright_black") if color else "(no results)"
        )


@cli.group()
def routing() -> None:
    """Routing tools and evaluation."""
    pass


@routing.command()
@click.option(
    "--dataset",
    type=click.Path(exists=True),
    required=True,
    help="Path to JSONL dataset",
)
@click.option("--top-k", default=10, help="Number of results to retrieve")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON")
def eval(dataset: str, top_k: int, as_json: bool) -> None:
    """Evaluate routing and retrieval quality."""
    if top_k < 1:
        click.echo("Top-k must be at least 1.", err=True)
        raise SystemExit(1)
    from llmc.rag.eval.routing_eval import evaluate_routing

    try:
        metrics = evaluate_routing(Path(dataset), top_k=top_k)

        if as_json:
            click.echo(json.dumps(metrics, indent=2))
        else:
            click.echo("=== Routing Evaluation Results ===")
            click.echo(f"Total Examples:     {metrics.get('total_examples', 0)}")
            if "error" in metrics:
                click.echo(f"Error: {metrics['error']}")
                return

            click.echo(f"Routing Accuracy:   {metrics['routing_accuracy']:.2%}")
            click.echo(f"Retrieval Hit@{top_k}:    {metrics['retrieval_hit_at_k']:.2%}")
            click.echo(f"Retrieval MRR:      {metrics['retrieval_mrr']:.4f}")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("show-weights")
@click.argument("path", required=False)
def show_weights(path: str | None) -> None:
    """Show configured path weights and priorities."""
    repo_root = _find_repo_root()
    try:
        # Import lazily
        from llmc.core import load_config as _load_llmc_config
        from llmc.enrichment import (
            classify_content_type,
            compute_final_priority,
            get_path_weight,
            load_path_weight_map,
        )

        cfg = _load_llmc_config(repo_root)
        weight_map = load_path_weight_map(cfg)

        click.echo(f"Loaded path weights from {repo_root / 'llmc.toml'}:")
        # Sort by weight (ascending = higher priority)
        sorted_weights = sorted(weight_map.items(), key=lambda x: x[1])
        for pattern, weight in sorted_weights:
            click.echo(f"  {pattern:<30} : {weight}")

        if path:
            weight, matched, winning = get_path_weight(path, weight_map)
            click.echo(f"\nAnalysis for '{path}':")
            click.echo(f"  Matched patterns: {matched}")
            click.echo(f"  Winning pattern:  {winning}")
            click.echo(f"  Path Weight:      {weight}")

            click.echo("\nPriorities:")
            for ctype in ["code", "docs"]:
                _, base = classify_content_type(ctype)
                final = compute_final_priority(base, weight)
                click.echo(f"  If {ctype:<5}: Base={base:<3} -> Final={final:.1f}")

    except ImportError:
        click.echo("Error: llmc package not available.", err=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


# ===========================================================================
# Sidecar Management Commands
# ===========================================================================

@cli.group(help="Manage document sidecars (PDF, DOCX → markdown conversion).")
def sidecar() -> None:
    """Document sidecar management."""
    pass


@sidecar.command("list")
@click.argument("path", required=False)
@click.option("--json", "as_json", is_flag=True, help="Emit as JSON.")
def sidecar_list(path: str | None, as_json: bool) -> None:
    """List all document sidecars and their freshness status."""
    repo_root = _find_repo_root()
    
    try:
        from .sidecar import get_sidecar_path, is_sidecar_stale
    except ImportError:
        click.echo("Error: Sidecar module not available.", err=True)
        sys.exit(1)
    
    sidecars_dir = repo_root / ".llmc" / "sidecars"
    if not sidecars_dir.exists():
        if as_json:
            click.echo(json.dumps({"sidecars": [], "summary": {"total": 0}}))
        else:
            click.echo("No sidecars found.")
        return
    
    results = []
    for sc in sorted(sidecars_dir.rglob("*.md.gz")):
        try:
            rel_sidecar = sc.relative_to(sidecars_dir)
            source_rel = str(rel_sidecar).removesuffix(".md.gz")
            source_path = repo_root / source_rel
            
            # Filter by path if specified
            if path and not source_rel.startswith(path):
                continue
            
            # Determine status
            if not source_path.exists():
                status = "orphan"
            elif is_sidecar_stale(Path(source_rel), repo_root):
                status = "stale"
            else:
                status = "fresh"
            
            size_kb = sc.stat().st_size / 1024
            results.append({
                "source": source_rel,
                "sidecar": str(sc.relative_to(repo_root)),
                "status": status,
                "size_kb": round(size_kb, 1),
            })
        except Exception:
            pass
    
    if as_json:
        summary = {
            "total": len(results),
            "fresh": sum(1 for r in results if r["status"] == "fresh"),
            "stale": sum(1 for r in results if r["status"] == "stale"),
            "orphan": sum(1 for r in results if r["status"] == "orphan"),
        }
        click.echo(json.dumps({"sidecars": results, "summary": summary}, indent=2))
    else:
        if not results:
            click.echo("No sidecars found.")
            return
        for r in results:
            status_icon = {"fresh": "✓", "stale": "!", "orphan": "×"}.get(r["status"], "?")
            click.echo(f"{status_icon} [{r['status']:<6}] {r['source']}")
        
        total = len(results)
        fresh = sum(1 for r in results if r["status"] == "fresh")
        stale = sum(1 for r in results if r["status"] == "stale")
        orphan = sum(1 for r in results if r["status"] == "orphan")
        click.echo(f"\nSummary: {total} sidecars ({fresh} fresh, {stale} stale, {orphan} orphan)")


@sidecar.command("clean")
@click.option("--dry-run", "-n", is_flag=True, help="Show what would be removed.")
@click.option("--json", "as_json", is_flag=True, help="Emit as JSON.")
def sidecar_clean(dry_run: bool, as_json: bool) -> None:
    """Remove orphaned sidecars (source files no longer exist)."""
    repo_root = _find_repo_root()
    
    try:
        from .sidecar import cleanup_orphan_sidecars
    except ImportError:
        click.echo("Error: Sidecar module not available.", err=True)
        sys.exit(1)
    
    sidecars_dir = repo_root / ".llmc" / "sidecars"
    if not sidecars_dir.exists():
        if as_json:
            click.echo(json.dumps({"orphans_removed": 0}))
        else:
            click.echo("No sidecars directory found.")
        return
    
    # Find orphans
    orphans = []
    for sc in sidecars_dir.rglob("*.md.gz"):
        try:
            rel_sidecar = sc.relative_to(sidecars_dir)
            source_rel = str(rel_sidecar).removesuffix(".md.gz")
            source_path = repo_root / source_rel
            if not source_path.exists():
                orphans.append(str(sc.relative_to(repo_root)))
        except Exception:
            pass
    
    if not orphans:
        if as_json:
            click.echo(json.dumps({"orphans_removed": 0, "orphans": []}))
        else:
            click.echo("✓ No orphaned sidecars found.")
        return
    
    if dry_run:
        if as_json:
            click.echo(json.dumps({"dry_run": True, "would_remove": orphans}))
        else:
            click.echo(f"Would remove {len(orphans)} orphaned sidecars:")
            for o in orphans:
                click.echo(f"  × {o}")
    else:
        removed = cleanup_orphan_sidecars(repo_root)
        if as_json:
            click.echo(json.dumps({"orphans_removed": removed}))
        else:
            click.echo(f"✓ Removed {removed} orphaned sidecars.")


@sidecar.command("generate")
@click.argument("path")
@click.option("--force", "-f", is_flag=True, help="Regenerate even if fresh.")
@click.option("--json", "as_json", is_flag=True, help="Emit as JSON.")
def sidecar_generate(path: str, force: bool, as_json: bool) -> None:
    """Generate or regenerate sidecar for a document or directory."""
    repo_root = _find_repo_root()
    
    try:
        from .sidecar import SidecarConverter, is_sidecar_eligible, is_sidecar_stale
    except ImportError:
        click.echo("Error: Sidecar module not available.", err=True)
        sys.exit(1)
    
    target = Path(path)
    if not target.is_absolute():
        target = repo_root / target
    
    if not target.exists():
        if as_json:
            click.echo(json.dumps({"error": f"Path not found: {path}"}))
        else:
            click.echo(f"Error: Path not found: {path}", err=True)
        sys.exit(1)
    
    # Collect files
    files_to_process = []
    if target.is_file():
        if is_sidecar_eligible(target):
            files_to_process.append(target)
    else:
        for ext in [".pdf", ".docx", ".pptx", ".rtf"]:
            for f in target.rglob(f"*{ext}"):
                if is_sidecar_eligible(f):
                    files_to_process.append(f)
    
    if not files_to_process:
        if as_json:
            click.echo(json.dumps({"generated": 0, "skipped": 0, "failed": 0}))
        else:
            click.echo("No eligible documents found.")
        return
    
    converter = SidecarConverter()
    generated = 0
    skipped = 0
    failed = 0
    results = []
    
    for file_path in files_to_process:
        try:
            rel_path = file_path.relative_to(repo_root)
        except ValueError:
            rel_path = file_path
        
        if not force and not is_sidecar_stale(rel_path, repo_root):
            skipped += 1
            results.append({"path": str(rel_path), "status": "skipped"})
            continue
        
        try:
            sc = converter.convert(rel_path, repo_root)
            if sc:
                generated += 1
                results.append({"path": str(rel_path), "status": "generated"})
            else:
                skipped += 1
                results.append({"path": str(rel_path), "status": "no_converter"})
        except Exception as e:
            failed += 1
            results.append({"path": str(rel_path), "status": "failed", "error": str(e)})
    
    if as_json:
        click.echo(json.dumps({
            "generated": generated,
            "skipped": skipped,
            "failed": failed,
            "results": results,
        }, indent=2))
    else:
        for r in results:
            if r["status"] == "generated":
                click.echo(f"✓ Generated: {r['path']}")
            elif r["status"] == "skipped":
                click.echo(f"- Skipped (fresh): {r['path']}")
            elif r["status"] == "failed":
                click.echo(f"✗ Failed: {r['path']} ({r.get('error', 'unknown')})")
        click.echo(f"\nSummary: {generated} generated, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    cli()
