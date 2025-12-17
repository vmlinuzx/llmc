"""
Model comparison analytics for enrichment quality and performance.

Provides commands to compare enrichment results between different LLM models,
track inference performance (T/s), and analyze quality differences.
"""

from pathlib import Path
import sqlite3
import statistics

import typer

from llmc.core import find_repo_root

# Default comparison columns
QUALITY_COLUMNS = ["summary", "tags", "evidence", "inputs", "outputs"]
METRICS_COLUMNS = ["tokens_per_second", "eval_count", "backend_host"]


def _find_rag_db(repo_path: Path) -> Path | None:
    """Find the RAG database in a repo."""
    candidates = [
        repo_path / ".rag" / "index_v2.db",
        repo_path / ".llmc" / "rag" / "index.db",
        repo_path / ".llmc" / "index_v2.db",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def compare_models(
    repo: Path | None = typer.Argument(
        None, help="Repository path (default: current directory)"
    ),
    baseline: Path | None = typer.Option(
        None, "--baseline", "-b", help="Baseline database to compare against"
    ),
    model_a: str | None = typer.Option(
        None,
        "--model-a",
        "-a",
        help="Model A to compare (default: most common in baseline)",
    ),
    model_b: str | None = typer.Option(
        None, "--model-b", help="Model B to compare (default: most common in current)"
    ),
    limit: int = typer.Option(
        5, "--limit", "-n", help="Number of side-by-side examples"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Compare enrichment quality between two models.

    Compares summary length, metadata richness, and shows side-by-side examples.
    Use --baseline to compare against a backup database.

    Examples:
        llmc analytics compare-models
        llmc analytics compare-models --baseline .rag/index_v2.db.backup
        llmc analytics compare-models -a qwen2.5:7b -b qwen3:4b
    """
    import json as json_lib

    repo_path = repo or find_repo_root()
    current_db = _find_rag_db(repo_path)

    if not current_db:
        typer.echo(f"Error: No RAG database found in {repo_path}", err=True)
        raise typer.Exit(1)

    # Connect to databases
    conn_current = sqlite3.connect(current_db)
    conn_baseline = None

    if baseline:
        if not baseline.exists():
            typer.echo(f"Error: Baseline database not found: {baseline}", err=True)
            raise typer.Exit(1)
        conn_baseline = sqlite3.connect(baseline)

    # Get model stats
    def get_model_stats(
        conn: sqlite3.Connection, model_filter: str | None = None
    ) -> dict:
        # Check if tokens_per_second column exists in this database
        cur = conn.execute("PRAGMA table_info(enrichments)")
        cols = {row[1] for row in cur.fetchall()}
        has_tps = "tokens_per_second" in cols

        # Build query with or without T/s column
        if has_tps:
            query = """
                SELECT 
                    model,
                    COUNT(*) as count,
                    AVG(LENGTH(summary)) as avg_summary,
                    AVG(LENGTH(tags)) as avg_tags,
                    AVG(LENGTH(evidence)) as avg_evidence,
                    AVG(LENGTH(inputs)) as avg_inputs,
                    AVG(LENGTH(outputs)) as avg_outputs,
                    SUM(CASE WHEN LENGTH(summary) = 0 OR summary IS NULL THEN 1 ELSE 0 END) as empty_summary,
                    AVG(tokens_per_second) as avg_tps
                FROM enrichments
                WHERE model IS NOT NULL
            """
        else:
            query = """
                SELECT 
                    model,
                    COUNT(*) as count,
                    AVG(LENGTH(summary)) as avg_summary,
                    AVG(LENGTH(tags)) as avg_tags,
                    AVG(LENGTH(evidence)) as avg_evidence,
                    AVG(LENGTH(inputs)) as avg_inputs,
                    AVG(LENGTH(outputs)) as avg_outputs,
                    SUM(CASE WHEN LENGTH(summary) = 0 OR summary IS NULL THEN 1 ELSE 0 END) as empty_summary,
                    NULL as avg_tps
                FROM enrichments
                WHERE model IS NOT NULL
            """
        if model_filter:
            query += f" AND model = '{model_filter}'"
        query += " GROUP BY model ORDER BY count DESC"

        cur = conn.execute(query)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        return rows

    # Get stats from both DBs
    current_stats = get_model_stats(conn_current)
    baseline_stats = get_model_stats(conn_baseline) if conn_baseline else []

    # Auto-select models if not specified
    if not model_b and current_stats:
        model_b = current_stats[0]["model"]
    if not model_a:
        if baseline_stats:
            model_a = baseline_stats[0]["model"]
        elif len(current_stats) > 1:
            model_a = current_stats[1]["model"]

    if json_output:
        result = {
            "current_db": str(current_db),
            "baseline_db": str(baseline) if baseline else None,
            "model_a": model_a,
            "model_b": model_b,
            "current_stats": current_stats,
            "baseline_stats": baseline_stats,
        }
        typer.echo(json_lib.dumps(result, indent=2, default=str))
        return

    # Print report
    typer.echo("=" * 80)
    typer.echo("ENRICHMENT MODEL COMPARISON")
    typer.echo("=" * 80)
    typer.echo(f"\nCurrent DB:  {current_db}")
    if baseline:
        typer.echo(f"Baseline DB: {baseline}")
    typer.echo(f"Model A:     {model_a or 'N/A'}")
    typer.echo(f"Model B:     {model_b or 'N/A'}")

    # Quantitative comparison
    typer.echo("\n" + "=" * 80)
    typer.echo("QUANTITATIVE COMPARISON")
    typer.echo("=" * 80)

    all_stats = baseline_stats + current_stats
    seen_models = set()

    typer.echo(
        f"\n{'Model':<35} {'Count':>8} {'Avg Summary':>12} {'Empty':>6} {'Avg T/s':>10}"
    )
    typer.echo("-" * 75)

    for stat in all_stats:
        model = stat["model"]
        if model in seen_models:
            continue
        seen_models.add(model)

        model_short = model[:33] + ".." if len(model) > 35 else model
        count = stat["count"]
        avg_summary = stat.get("avg_summary") or 0
        empty = stat.get("empty_summary") or 0
        avg_tps = stat.get("avg_tps") or 0

        tps_str = f"{avg_tps:.1f}" if avg_tps else "N/A"
        typer.echo(
            f"{model_short:<35} {count:>8} {avg_summary:>12.1f} {empty:>6} {tps_str:>10}"
        )

    # Comparison ratio if both models exist
    if model_a and model_b:
        stat_a = next((s for s in all_stats if s["model"] == model_a), None)
        stat_b = next((s for s in all_stats if s["model"] == model_b), None)

        if stat_a and stat_b:
            typer.echo("\n" + "=" * 80)
            typer.echo(f"HEAD-TO-HEAD: {model_a} vs {model_b}")
            typer.echo("=" * 80)

            for metric in [
                "avg_summary",
                "avg_tags",
                "avg_evidence",
                "avg_inputs",
                "avg_outputs",
            ]:
                val_a = stat_a.get(metric) or 0
                val_b = stat_b.get(metric) or 0
                ratio = val_b / val_a if val_a > 0 else 0
                label = metric.replace("avg_", "").title()
                typer.echo(
                    f"  {label:<12}: {val_a:>8.1f} → {val_b:>8.1f}  ({ratio:.2f}x)"
                )

            # T/s comparison
            tps_a = stat_a.get("avg_tps") or 0
            tps_b = stat_b.get("avg_tps") or 0
            if tps_a > 0 and tps_b > 0:
                tps_ratio = tps_b / tps_a
                typer.echo(
                    f"\n  T/s (speed): {tps_a:>8.1f} → {tps_b:>8.1f}  ({tps_ratio:.2f}x)"
                )

    # Side-by-side examples
    if baseline and model_a and model_b and limit > 0:
        typer.echo("\n" + "=" * 80)
        typer.echo(f"SIDE-BY-SIDE EXAMPLES ({limit} samples)")
        typer.echo("=" * 80)

        # Find common span_hashes
        cur_a = conn_baseline.execute(
            "SELECT span_hash FROM enrichments WHERE model = ? AND LENGTH(summary) > 50 ORDER BY RANDOM() LIMIT ?",
            (model_a, limit * 10),
        )
        hashes_a = set(row[0] for row in cur_a.fetchall())

        cur_b = conn_current.execute(
            "SELECT span_hash FROM enrichments WHERE model = ? AND LENGTH(summary) > 50",
            (model_b,),
        )
        hashes_b = set(row[0] for row in cur_b.fetchall())

        common = list(hashes_a & hashes_b)[:limit]

        for span_hash in common:
            # Get enrichments
            row_a = conn_baseline.execute(
                "SELECT summary, tags FROM enrichments WHERE span_hash = ?",
                (span_hash,),
            ).fetchone()
            row_b = conn_current.execute(
                "SELECT summary, tags FROM enrichments WHERE span_hash = ?",
                (span_hash,),
            ).fetchone()

            if row_a and row_b:
                typer.echo(f"\n--- {span_hash[:50]}... ---")
                typer.echo(f"\n[{model_a}] ({len(row_a[0] or '')} chars):")
                typer.echo(f"  {(row_a[0] or '')[:200]}...")
                typer.echo(f"\n[{model_b}] ({len(row_b[0] or '')} chars):")
                typer.echo(f"  {(row_b[0] or '')[:200]}...")

    conn_current.close()
    if conn_baseline:
        conn_baseline.close()


def metrics(
    repo: Path | None = typer.Argument(
        None, help="Repository path (default: current directory)"
    ),
    model: str | None = typer.Option(None, "--model", "-m", help="Filter by model"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Analyze enrichment performance metrics (T/s, token counts).

    Shows inference speed statistics for each model and backend.

    Examples:
        llmc analytics metrics
        llmc analytics metrics --model qwen3:4b
    """
    import json as json_lib

    repo_path = repo or find_repo_root()
    db_path = _find_rag_db(repo_path)

    if not db_path:
        typer.echo(f"Error: No RAG database found in {repo_path}", err=True)
        raise typer.Exit(1)

    conn = sqlite3.connect(db_path)

    # Check if metrics columns exist
    cur = conn.execute("PRAGMA table_info(enrichments)")
    cols = {row[1] for row in cur.fetchall()}

    if "tokens_per_second" not in cols:
        typer.echo("No performance metrics found in database.")
        typer.echo(
            "New enrichments will include metrics after updating to latest LLMC."
        )
        raise typer.Exit(0)

    # Query metrics
    query = """
        SELECT 
            model,
            backend_host,
            tokens_per_second,
            eval_count,
            prompt_eval_count,
            total_duration_ns
        FROM enrichments
        WHERE tokens_per_second IS NOT NULL
    """
    if model:
        query += f" AND model = '{model}'"

    cur = conn.execute(query)
    rows = cur.fetchall()

    if not rows:
        typer.echo("No enrichments with performance metrics found yet.")
        raise typer.Exit(0)

    # Group by model
    model_data: dict[str, list[dict]] = {}
    for m, host, tps, eval_count, prompt_count, total_dur in rows:
        if m not in model_data:
            model_data[m] = []
        model_data[m].append(
            {
                "tps": tps,
                "eval_count": eval_count or 0,
                "prompt_count": prompt_count or 0,
                "total_dur": total_dur or 0,
                "host": host or "unknown",
            }
        )

    if json_output:
        result = {"models": {}}
        for m, data in model_data.items():
            tps_values = [d["tps"] for d in data if d["tps"] and d["tps"] > 0]
            result["models"][m] = {
                "count": len(data),
                "avg_tps": statistics.mean(tps_values) if tps_values else 0,
                "min_tps": min(tps_values) if tps_values else 0,
                "max_tps": max(tps_values) if tps_values else 0,
                "total_tokens": sum(d["eval_count"] for d in data),
            }
        typer.echo(json_lib.dumps(result, indent=2))
        return

    # Print report
    typer.echo("=" * 80)
    typer.echo("ENRICHMENT PERFORMANCE METRICS")
    typer.echo("=" * 80)

    typer.echo(
        f"\n{'Model':<40} {'Count':>8} {'Avg T/s':>10} {'Min T/s':>10} {'Max T/s':>10}"
    )
    typer.echo("-" * 80)

    for m, data in sorted(model_data.items(), key=lambda x: -len(x[1])):
        tps_values = [d["tps"] for d in data if d["tps"] and d["tps"] > 0]
        if not tps_values:
            continue

        model_short = m[:38] + ".." if len(m) > 40 else m
        avg_tps = statistics.mean(tps_values)
        min_tps = min(tps_values)
        max_tps = max(tps_values)

        typer.echo(
            f"{model_short:<40} {len(data):>8} {avg_tps:>10.1f} {min_tps:>10.1f} {max_tps:>10.1f}"
        )

    # Performance tiers
    typer.echo("\n" + "-" * 80)
    typer.echo("PERFORMANCE CLASSIFICATION")
    typer.echo("-" * 80)

    for m, data in sorted(model_data.items(), key=lambda x: -len(x[1])):
        tps_values = [d["tps"] for d in data if d["tps"] and d["tps"] > 0]
        if not tps_values:
            continue

        avg_tps = statistics.mean(tps_values)

        if avg_tps < 5:
            tier = "🐢 Very Slow (likely CPU)"
        elif avg_tps < 15:
            tier = "🐇 Slow (entry GPU or CPU)"
        elif avg_tps < 30:
            tier = "⚡ Moderate (typical GPU)"
        elif avg_tps < 60:
            tier = "🚀 Fast (good GPU)"
        else:
            tier = "🔥 Very Fast (high-end GPU)"

        model_short = m[:35] if len(m) <= 35 else m[:33] + ".."
        typer.echo(f"  {model_short}: {avg_tps:.1f} T/s → {tier}")

    conn.close()
