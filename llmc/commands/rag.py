import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer

from llmc.core import find_repo_root


def index(
    since: Annotated[
        str | None, typer.Option(help="Only parse files changed since the given commit")
    ] = None,
    no_export: Annotated[bool, typer.Option(help="Skip JSONL span export")] = False,
):
    """Index the repository (full or incremental)."""
    from llmc.rag.indexer import index_repo as run_index_repo

    try:
        stats = run_index_repo(since=since, export_json=not no_export)
        typer.echo(
            f"Indexed {stats['files']} files, {stats['spans']} spans in {stats.get('duration_sec', 0):.2f}s "
            f"(skipped={stats.get('skipped', 0)}, unchanged={stats.get('unchanged', 0)})"
        )
    except Exception as e:
        typer.echo(f"Error indexing repo: {e}", err=True)
        raise typer.Exit(code=1) from e


def search(
    query: str,
    limit: Annotated[int, typer.Option(help="Max results")] = 10,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
):
    """Semantic search."""
    from llmc.rag.search import search_spans as run_search_spans

    # Input validation
    if limit <= 0:
        typer.echo("Error: --limit must be a positive integer", err=True)
        raise typer.Exit(code=1)

    # Prevent excessively long queries that cause timeout
    MAX_QUERY_LENGTH = 5000  # Reasonable limit for semantic search
    if len(query) > MAX_QUERY_LENGTH:
        typer.echo(
            f"Error: Query too long ({len(query)} chars). Maximum allowed: {MAX_QUERY_LENGTH} chars",
            err=True,
        )
        typer.echo("Consider using a shorter, more focused query", err=True)
        raise typer.Exit(code=1)

    repo_root = find_repo_root()
    try:
        results = run_search_spans(query, limit=limit, repo_root=repo_root)
        if json_output:
            data = [
                {
                    "score": r.score,
                    "file": str(r.path),
                    "line": r.start_line,
                    "symbol": r.symbol,
                    "kind": r.kind,
                    "summary": r.summary,
                }
                for r in results
            ]
            typer.echo(json.dumps(data, indent=2))
        else:
            for r in results:
                typer.echo(
                    f"[{r.score:.2f}] {r.path}:{r.start_line} {r.symbol or '(no symbol)'}"
                )
                if r.summary:
                    typer.echo(f"    {r.summary[:100]}...")
    except Exception as e:
        typer.echo(f"Error searching: {e}", err=True)
        raise typer.Exit(code=1) from e


def inspect(
    symbol: Annotated[
        str | None, typer.Option("--symbol", "-s", help="Symbol to inspect")
    ] = None,
    path: Annotated[str | None, typer.Option("--path", "-p", help="File path")] = None,
    line: Annotated[
        int | None, typer.Option("--line", "-l", help="Line number")
    ] = None,
    full: Annotated[
        bool, typer.Option("--full", help="Include full source code")
    ] = False,
):
    """Deep dive into symbol/file."""
    from llmc.rag.inspector import inspect_entity as run_inspect_entity

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
            include_full_source=full,
        )
        typer.echo(result)
    except Exception as e:
        typer.echo(f"Error inspecting: {e}", err=True)
        raise typer.Exit(code=1) from e


def plan(
    query: str,
    limit: Annotated[int, typer.Option(help="Max files/spans")] = 50,
    min_confidence: Annotated[
        float, typer.Option(help="Minimum confidence threshold")
    ] = 0.6,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit plan as JSON")
    ] = False,
):
    """Generate retrieval plan."""
    from llmc.rag.planner import generate_plan as run_generate_plan, plan_as_dict

    repo_root = find_repo_root()
    try:
        result = run_generate_plan(
            query=query, limit=limit, min_confidence=min_confidence, repo_root=repo_root
        )
        if json_output:
            typer.echo(json.dumps(plan_as_dict(result), indent=2, ensure_ascii=False))
        else:
            # Human-readable summary
            typer.echo(f"Query: {result.query}")
            typer.echo(f"Intent: {result.intent}")
            typer.echo(f"Confidence: {result.confidence:.2%}")
            typer.echo(f"Fallback recommended: {result.fallback_recommended}")
            typer.echo(f"\nTop {len(result.spans)} spans:")
            for i, span in enumerate(result.spans, 1):
                typer.echo(f"  {i}. [{span.score:.1f}] {span.path}:{span.lines[0]}-{span.lines[1]} {span.symbol}")
            if result.rationale:
                typer.echo(f"\nRationale: {'; '.join(result.rationale[:3])}")
    except Exception as e:
        typer.echo(f"Error planning: {e}", err=True)
        raise typer.Exit(code=1) from e


def stats(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit stats as JSON.")
    ] = False,
):
    """Print summary stats for the current index."""
    from llmc.rag.config import get_est_tokens_per_span, index_path_for_read
    from llmc.rag.database import Database

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

    # Add Tool Stats from Telemetry DB
    telemetry_db = repo_root / ".llmc" / "telemetry.db"
    tool_stats = {"total_calls": 0, "total_errors": 0, "top_tools": []}

    if telemetry_db.exists():
        try:
            import sqlite3

            with sqlite3.connect(telemetry_db) as conn:
                # Total calls
                row = conn.execute("SELECT COUNT(*) FROM tool_usage").fetchone()
                if row:
                    tool_stats["total_calls"] = row[0]

                # Total errors
                row = conn.execute(
                    "SELECT COUNT(*) FROM tool_usage WHERE success = 0"
                ).fetchone()
                if row:
                    tool_stats["total_errors"] = row[0]

                # Top tools
                rows = conn.execute(
                    """
                    SELECT tool, COUNT(*) as c 
                    FROM tool_usage 
                    GROUP BY tool 
                    ORDER BY c DESC 
                    LIMIT 5
                """
                ).fetchall()
                tool_stats["top_tools"] = [{"tool": r[0], "calls": r[1]} for r in rows]

            data["tool_stats"] = tool_stats
        except Exception:
            pass

    if json_output:
        typer.echo(json.dumps(data, indent=2))
    else:
        typer.echo(f"Repo: {data['repo']}")
        typer.echo(f"Files: {data['files']}")
        typer.echo(f"Spans: {data['spans']}")
        typer.echo(f"Embeddings: {data['embeddings']}")
        typer.echo(f"Enrichments: {data['enrichments']}")
        typer.echo(f"Est. Remote Tokens: {data['estimated_remote_tokens']:,}")

        if tool_stats["total_calls"] > 0:
            typer.echo("\nTool Usage:")
            typer.echo(f"  Total Calls: {tool_stats['total_calls']}")
            typer.echo(f"  Errors: {tool_stats['total_errors']}")
            typer.echo("  Top Tools:")
            for t in tool_stats["top_tools"]:
                typer.echo(f"    - {t['tool']}: {t['calls']}")


def doctor(
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Verbose output")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit report as JSON")
    ] = False,
):
    """Diagnose RAG health."""
    from llmc.rag.doctor import run_rag_doctor as run_doctor

    repo_root = find_repo_root()
    result = run_doctor(repo_path=repo_root, verbose=verbose)

    if json_output:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # Human-readable output
    status = result.get("status", "UNKNOWN")
    status_icon = {"OK": "✅", "WARN": "⚠️", "EMPTY": "📭", "NO_DB": "❌"}.get(status, "❓")
    typer.echo(f"{status_icon} RAG Health: {status}")
    typer.echo(f"   Repo: {result.get('repo')}")
    typer.echo(f"   DB: {result.get('db_path')}")

    stats = result.get("stats")
    if stats:
        typer.echo(f"\n📊 Stats:")
        typer.echo(f"   Files: {stats.get('files', 0)}")
        typer.echo(f"   Spans: {stats.get('spans', 0)}")
        typer.echo(f"   Enrichments: {stats.get('enrichments', 0)} (pending: {stats.get('pending_enrichments', 0)})")
        typer.echo(f"   Embeddings: {stats.get('embeddings', 0)} (pending: {stats.get('pending_embeddings', 0)})")
        if stats.get('orphan_enrichments', 0) > 0:
            typer.echo(f"   ⚠️ Orphan enrichments: {stats.get('orphan_enrichments')}")

    issues = result.get("issues", [])
    if issues:
        typer.echo(f"\n⚠️ Issues:")
        for issue in issues:
            typer.echo(f"   • {issue}")

    top_pending = result.get("top_pending_files", [])
    if top_pending:
        typer.echo(f"\n📋 Top pending files:")
        for f in top_pending:
            typer.echo(f"   • {f['path']} ({f['pending_spans']} spans)")


# Phase 5: Advanced RAG Commands


def sync(
    paths: Annotated[
        list[str] | None, typer.Option("--path", help="Specific file paths to sync")
    ] = None,
    since: Annotated[
        str | None, typer.Option(help="Sync files changed since commit")
    ] = None,
    stdin: Annotated[
        bool, typer.Option("--stdin", help="Read paths from stdin")
    ] = False,
):
    """Incrementally update spans for selected files."""
    from llmc.rag.indexer import sync_paths
    from llmc.rag.utils import git_changed_paths

    repo_root = find_repo_root()

    # Determine which files to sync
    path_list = []
    if since:
        path_list = git_changed_paths(repo_root, since)
    elif paths:
        path_list = [Path(p) for p in paths]
    elif stdin:
        import sys

        for raw_line in sys.stdin:
            line = raw_line.strip()
            if line:
                path_list.append(Path(line))

    if not path_list:
        typer.echo("No paths to sync. Use --path, --since, or --stdin")
        raise typer.Exit(code=1)

    try:
        stats = sync_paths(path_list)
        typer.echo(
            f"Synced {stats['files']} files, {stats['spans']} spans, "
            f"deleted={stats.get('deleted', 0)}, unchanged={stats.get('unchanged', 0)} "
            f"in {stats['duration_sec']:.2f}s"
        )
    except Exception as e:
        typer.echo(f"Error syncing: {e}", err=True)
        raise typer.Exit(code=1) from e


def enrich(
    limit: Annotated[int, typer.Option(help="Max spans to enrich")] = 10,
    dry_run: Annotated[
        bool, typer.Option(help="Preview work items without running LLM")
    ] = False,
    model: Annotated[str, typer.Option(help="Model identifier")] = "local-qwen",
    cooldown: Annotated[
        int, typer.Option(help="Skip spans changed within N seconds")
    ] = 0,
    code_first: Annotated[
        bool,
        typer.Option(
            "--code-first",
            help="Use code-first prioritization for enrichment (overrides config).",
        ),
    ] = False,
    no_code_first: Annotated[
        bool,
        typer.Option(
            "--no-code-first",
            help="Disable code-first prioritization and use legacy ordering.",
        ),
    ] = False,
    starvation_ratio: Annotated[
        str,
        typer.Option(
            "--starvation-ratio",
            help="High:Low ratio for mixing high/low priority tasks when code-first is enabled (e.g. 5:1).",
        ),
    ] = "5:1",
    show_weights: Annotated[
        bool,
        typer.Option(
            "--show-weights",
            help="In dry-run mode, include path weights and priority scoring.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Emit machine-readable JSON (primarily for dry-run / --show-weights).",
        ),
    ] = False,
):
    """Preview or execute enrichment tasks (summary/tags)."""
    from llmc.core import load_config
    from llmc.enrichment import FileClassifier, load_path_weight_map
    from llmc.rag.config import index_path_for_read
    from llmc.rag.database import Database
    from llmc.rag.types import SpanWorkItem
    from llmc.rag.workers import (
        default_enrichment_callable,
        enrichment_plan,
        execute_enrichment,
    )

    repo_root = find_repo_root()

    # Resolve code-first override and starvation ratio.
    if code_first and no_code_first:
        typer.echo(
            "Error: cannot pass both --code-first and --no-code-first.", err=True
        )
        raise typer.Exit(code=1)

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
        except Exception as e:
            typer.echo(
                "Error: invalid --starvation-ratio value. Expected format HIGH:LOW (e.g. 5:1).",
                err=True,
            )
            raise typer.Exit(code=1) from e

    db_file = index_path_for_read(repo_root)
    if not db_file.exists():
        typer.echo("No index database found. Run `llmc index` first.")
        raise typer.Exit(code=1)

    db = Database(db_file)
    try:
        if dry_run:
            plan = enrichment_plan(
                db, repo_root, limit=limit, cooldown_seconds=cooldown
            )
            if not plan:
                typer.echo("No spans pending enrichment.")
                return

            if show_weights:
                cfg = load_config(repo_root)
                weight_map = load_path_weight_map(cfg)

                rag_db = Database(db_file)
                try:
                    pending: list[SpanWorkItem] = rag_db.pending_enrichments(
                        limit=limit, cooldown_seconds=cooldown
                    )
                finally:
                    rag_db.close()

                pending_by_hash: dict[str, SpanWorkItem] = {
                    item.span_hash: item for item in pending
                }
                classifier = FileClassifier(
                    repo_root=repo_root, weight_config=weight_map
                )

                enriched_plan: list[dict] = []
                for entry in plan:
                    span_hash = cast(str, entry.get("span_hash"))
                    work_item = pending_by_hash.get(span_hash)
                    if work_item is None:
                        enriched_plan.append(entry)
                        continue
                    decision = classifier.classify_span(work_item)
                    enriched_entry = {
                        **entry,
                        "weight": decision.weight,
                        "matched_patterns": list(decision.matched_patterns),
                        "winning_pattern": decision.winning_pattern,
                        "base_priority": decision.base_priority,
                        "final_priority": decision.final_priority,
                    }
                    enriched_plan.append(enriched_entry)

                plan = enriched_plan

            typer.echo(json.dumps(plan, indent=2, ensure_ascii=False))
            typer.echo(
                "\n(Dry run only. Remove --dry-run to persist enrichment results.)"
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
        typer.echo(f"✅ Stored enrichment metadata for {successes} spans using {model}")
    else:
        typer.echo("No spans enriched.")

    if errors:
        for err in errors:
            typer.echo(f"❌ ERROR: {err}", err=True)
        raise typer.Exit(code=1)


def embed(
    limit: Annotated[int, typer.Option(help="Max spans to embed")] = 10,
    dry_run: Annotated[
        bool, typer.Option(help="Preview work items without generating embeddings")
    ] = False,
    model: Annotated[
        str, typer.Option(help="Embedding model (auto uses configured default)")
    ] = "auto",
    dim: Annotated[
        int, typer.Option(help="Embedding dimension (0 uses model default)")
    ] = 0,
):
    """Preview or execute embedding jobs for spans."""
    from llmc.rag.config import index_path_for_read
    from llmc.rag.database import Database
    from llmc.rag.workers import embedding_plan, execute_embeddings

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
            plan = embedding_plan(
                db, repo_root, limit=limit, model=model_arg, dim=dim_arg
            )
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
        typer.echo(
            f"✅ Stored embeddings for {len(results)} spans using {used_model} (dim={used_dim})"
        )


def graph(
    require_enrichment: Annotated[
        bool, typer.Option(help="Require enrichment data in index")
    ] = True,
    output: Annotated[
        Path | None, typer.Option(help="Output path (default: .llmc/rag_graph.json)")
    ] = None,
):
    """Build a schema graph for the current repository."""
    from llmc.rag.schema import build_graph_for_repo as schema_build_graph_for_repo

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
        raise typer.Exit(code=1) from err
    except FileNotFoundError as err:
        typer.echo(str(err), err=True)
        raise typer.Exit(code=1) from err

    graph_obj.save(output)
    typer.echo(f"✅ Wrote graph JSON to {output}")


def enrich_status(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit enrichment runner metrics as JSON.")
    ] = False,
):
    """Show enrichment runner metrics and code-first status for this repo."""
    repo_root = find_repo_root()

    summary_path = repo_root / ".llmc" / "enrich_summary.json"
    metrics_path = repo_root / "logs" / "enrichment_metrics.jsonl"

    summary: dict[str, Any] | None = None
    if summary_path.exists():
        try:
            with summary_path.open("r", encoding="utf-8") as fh:
                summary = json.load(fh)
        except Exception:
            summary = None

    if summary is None and not metrics_path.exists():
        typer.echo(
            "No enrichment metrics found for this repo. "
            "Run the RAG service or `llmc service start` to generate enrichment data."
        )
        raise typer.Exit(code=1)

    if summary is None:
        # Fallback: derive a minimal summary from metrics JSONL.
        files_by_weight: dict[int, int] = {}
        runner_modes: set[str] = set()
        high_timestamps: list[str] = []
        first_timestamp: str | None = None

        try:
            with metrics_path.open("r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue

                    if str(rec.get("repo_root")) != str(repo_root):
                        continue

                    ts = rec.get("timestamp")
                    if isinstance(ts, str) and not first_timestamp:
                        first_timestamp = ts

                    mode = rec.get("runner_mode")
                    if isinstance(mode, str):
                        runner_modes.add(mode)

                    if not rec.get("schema_ok", False):
                        continue

                    weight = rec.get("path_weight")
                    if isinstance(weight, int) and 1 <= weight <= 10:
                        files_by_weight[weight] = files_by_weight.get(weight, 0) + 1

                    if rec.get("weight_tier") == "high" and isinstance(ts, str):
                        high_timestamps.append(ts)
        except Exception:
            files_by_weight = {}

        # Compute simple timing metrics if timestamps are available.
        time_to_first_high: float | None = None
        if first_timestamp and high_timestamps:
            try:
                from datetime import datetime

                base = datetime.fromisoformat(first_timestamp)
                first_high = min(datetime.fromisoformat(t) for t in high_timestamps)
                time_to_first_high = (first_high - base).total_seconds()
            except Exception:
                time_to_first_high = None

        summary = {
            "repo_root": str(repo_root),
            "runner_mode": next(iter(runner_modes)) if runner_modes else "unknown",
            "files_enriched_by_weight": files_by_weight,
        }
        if time_to_first_high is not None:
            summary["time_to_first_high_priority"] = time_to_first_high

    if json_output:
        typer.echo(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    # Human-readable output
    repo_name = Path(str(summary.get("repo_root", repo_root))).name
    runner_mode = summary.get("runner_mode", "unknown")
    files_by_weight = cast(
        dict[int, int], summary.get("files_enriched_by_weight", {}) or {}
    )
    queue_by_tier = cast(
        dict[str, int], summary.get("queue_depth_by_weight_tier", {}) or {}
    )
    t_first = summary.get("time_to_first_high_priority")
    t_all = summary.get("time_to_all_high_priority")

    typer.echo(f"Repo: {repo_name}")
    typer.echo(f"Runner mode: {runner_mode}")

    if files_by_weight:
        typer.echo("Files enriched by weight:")
        for w in sorted(int(k) for k in files_by_weight.keys()):
            count = files_by_weight.get(w, 0)
            typer.echo(f"  weight {w}: {count}")
    else:
        typer.echo("Files enriched by weight: (no data)")

    if queue_by_tier:
        typer.echo("Queue depth by tier (approximate):")
        for tier in ("high", "medium", "low"):
            val = queue_by_tier.get(tier, 0)
            typer.echo(f"  {tier}: {val}")

    if isinstance(t_first, (int, float)):
        typer.echo(f"Time to first high-priority enrichment: {t_first:.2f}s")
    if isinstance(t_all, (int, float)):
        typer.echo(f"Time to all high-priority enrichments: {t_all:.2f}s")


def file_descriptions(
    mode: Annotated[
        str, typer.Option(help="Generation mode: 'cheap' (span compression) or 'rich' (LLM)")
    ] = "cheap",
    force: Annotated[
        bool, typer.Option(help="Force regeneration even if descriptions are fresh")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit results as JSON")
    ] = False,
):
    """Generate stable file-level descriptions for mcgrep and LLM context.
    
    This command creates ~50 word descriptions for each file based on its
    enriched spans. The descriptions are cached and only regenerated when
    the file content or its spans change.
    
    Modes:
        cheap: Compress top span summaries (fast, no LLM)
        rich: Use LLM to generate descriptions (slower, better quality)
    """
    from llmc.rag.config import index_path_for_read
    from llmc.rag.database import Database
    from llmc.rag.enrichment.file_descriptions import generate_all_file_descriptions

    repo_root = find_repo_root()
    db_file = index_path_for_read(repo_root)
    if not db_file.exists():
        typer.echo("No index database found. Run `llmc index` first.")
        raise typer.Exit(code=1)

    db = Database(db_file)
    try:
        def progress_callback(current: int, total: int) -> None:
            if not json_output:
                typer.echo(f"\r  Processing: {current}/{total} files", nl=False)

        results = generate_all_file_descriptions(
            db=db,
            repo_root=repo_root,
            mode=mode,
            force=force,
            progress_callback=progress_callback if not json_output else None,
        )
    finally:
        db.close()

    if json_output:
        typer.echo(json.dumps(results, indent=2))
    else:
        typer.echo()  # newline after progress
        typer.echo(f"✅ File descriptions: {results['updated']} updated, {results['skipped']} skipped, {results['failed']} failed")
        if results['updated'] > 0:
            typer.echo(f"   Mode: {mode}")
        if force:
            typer.echo("   (forced regeneration)")


def export(
    output: Annotated[
        str | None, typer.Option("-o", "--output", help="Output archive path")
    ] = None,
):
    """Export all RAG data to tar.gz archive."""
    from llmc.rag.export_data import run_export

    repo_root = find_repo_root()
    output_path = Path(output) if output else None
    run_export(repo_root=repo_root, output_path=output_path)


def benchmark(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit metrics as JSON")
    ] = False,
    top1_threshold: Annotated[
        float, typer.Option(help="Minimum top-1 accuracy required")
    ] = 0.75,
    margin_threshold: Annotated[
        float, typer.Option(help="Minimum avg positive-minus-negative margin")
    ] = 0.1,
):
    """Run a lightweight embedding quality benchmark."""
    from llmc.rag.benchmark import run_embedding_benchmark

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

    if json_output:
        typer.echo(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        typer.echo("Embedding benchmark results:")
        typer.echo(f"  cases           : {int(report['cases'])}")
        typer.echo(
            f"  top1_accuracy   : {report['top1_accuracy']:.3f} (threshold {top1_threshold:.2f})"
        )
        typer.echo(
            f"  avg_margin      : {report['avg_margin']:.3f} (threshold {margin_threshold:.2f})"
        )
        typer.echo(f"  avg_positive    : {report['avg_positive_score']:.3f}")
        typer.echo(f"  avg_negative    : {report['avg_negative_score']:.3f}")
        typer.echo(f"  status          : {'✅ PASS' if success else '❌ FAIL'}")

    if not success:
        raise typer.Exit(code=1)


# Nav subcommand group
def nav_search(
    query: str,
    limit: Annotated[int, typer.Option("-n", "--limit", help="Max results")] = 10,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit JSON output")
    ] = False,
):
    """Semantic/structural search using graph when fresh, else local fallback."""
    from llmc.rag import tool_rag_search

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
                            },
                        },
                    }
                    for it in result.items
                ],
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
        raise typer.Exit(code=1) from e


def nav_where_used(
    symbol: str,
    limit: Annotated[int, typer.Option(help="Max results")] = 10,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit JSON output")
    ] = False,
):
    """Find where a symbol is used (callers, importers)."""
    from llmc.rag import tool_rag_where_used

    repo_root = find_repo_root()

    try:
        result = tool_rag_where_used(symbol, repo_root=repo_root, limit=limit)

        if json_output:
            typer.echo(json.dumps(result.to_dict(), indent=2, default=str))
        else:
            typer.echo(f"Where-used results for '{symbol}':")
            if not result.items:
                typer.echo("  No usages found.")
            else:
                for i, item in enumerate(result.items, 1):
                    loc = item.snippet.location
                    typer.echo(f"{i}. {loc.path}:{loc.start_line}-{loc.end_line}")
                    text = item.snippet.text
                    if text:
                        typer.echo(f"   {text[:80]}..." if len(text) > 80 else f"   {text}")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from e


def nav_lineage(
    symbol: str,
    depth: Annotated[int, typer.Option(help="Max depth to traverse")] = 2,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit JSON output")
    ] = False,
):
    """Show symbol lineage (parents, children, dependencies)."""
    from llmc.rag import tool_rag_lineage

    repo_root = find_repo_root()

    try:
        # Default to downstream for now, mapping depth to max_results as legacy adapter
        result = tool_rag_lineage(
            symbol, direction="downstream", repo_root=repo_root, max_results=depth
        )

        if json_output:
            typer.echo(json.dumps(result.to_dict(), indent=2, default=str))
        else:
            typer.echo(f"Lineage for '{symbol}' ({result.direction}):")
            if not result.items:
                typer.echo("  No lineage found.")
            else:
                for i, item in enumerate(result.items, 1):
                    loc = item.snippet.location
                    typer.echo(f"{i}. {loc.path}:{loc.start_line}-{loc.end_line}")
                    text = item.snippet.text
                    if text:
                        typer.echo(f"   {text[:80]}..." if len(text) > 80 else f"   {text}")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from e
