#!/usr/bin/env python3
"""
RAG Doctor – lightweight health and stats for the RAG index.

Provides:
- run_rag_doctor(repo_path) -> dict
- format_rag_doctor_summary(report, repo_name) -> str
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.rag.config import index_path_for_read
from tools.rag.database import Database


def _open_db(repo_path: Path) -> tuple[Database | None, Path]:
    """Open the RAG index database for read-only diagnostics."""
    db_path = index_path_for_read(repo_path)
    if not db_path.exists():
        return None, db_path
    return Database(db_path), db_path


def run_rag_doctor(repo_path: Path, verbose: bool = False) -> dict[str, Any]:
    """
    Inspect the RAG index and return a structured health report.

    The report schema is intentionally JSON-friendly:

    {
      "status": "OK" | "EMPTY" | "NO_DB" | "WARN",
      "repo": "<absolute repo path>",
      "db_path": "<index db path or None>",
      "timestamp": "<ISO8601>",
      "stats": {
         "files": int,
         "spans": int,
         "enrichments": int,
         "embeddings": int,
         "pending_enrichments": int,
         "pending_embeddings": int,
         "orphan_enrichments": int
      },
      "top_pending_files": [
         {"path": "<relative path>", "pending_spans": int},
         ...
      ],
      "issues": [ "human-readable summary strings" ]
    }
    """
    repo_path = repo_path.resolve()
    db, db_path = _open_db(repo_path)
    now = datetime.now(UTC).isoformat()

    if db is None:
        return {
            "status": "NO_DB",
            "repo": str(repo_path),
            "db_path": str(db_path),
            "timestamp": now,
            "stats": None,
            "top_pending_files": [],
            "issues": ["RAG index database does not exist for this repo."],
        }

    try:
        base_stats = db.stats()  # files, spans, enrichments, embeddings
        conn = db.conn

        # Count spans that still need enrichment.
        pending_enrichments = conn.execute(
            """
            SELECT COUNT(*)
            FROM spans
            LEFT JOIN enrichments ON spans.span_hash = enrichments.span_hash
            WHERE enrichments.span_hash IS NULL
            """
        ).fetchone()[0]

        # Count spans that still need embeddings (default profile).
        pending_embeddings = conn.execute(
            """
            SELECT COUNT(*)
            FROM spans
            LEFT JOIN embeddings
                ON spans.span_hash = embeddings.span_hash
               AND embeddings.profile = 'default'
            WHERE embeddings.span_hash IS NULL
            """
        ).fetchone()[0]

        # Safety check: enrichments that no longer have a backing span.
        orphan_enrichments = conn.execute(
            """
            SELECT COUNT(*)
            FROM enrichments
            LEFT JOIN spans ON spans.span_hash = enrichments.span_hash
            WHERE spans.span_hash IS NULL
            """
        ).fetchone()[0]

        top_pending_files: list[dict[str, Any]] = []
        if verbose or pending_enrichments:
            rows = conn.execute(
                """
                SELECT files.path AS path, COUNT(*) AS pending_spans
                FROM spans
                JOIN files ON spans.file_id = files.id
                LEFT JOIN enrichments ON spans.span_hash = enrichments.span_hash
                WHERE enrichments.span_hash IS NULL
                GROUP BY files.id
                ORDER BY pending_spans DESC
                LIMIT 5
                """
            ).fetchall()
            for row in rows:
                top_pending_files.append(
                    {
                        "path": row["path"],
                        "pending_spans": int(row["pending_spans"]),
                    }
                )

        # Derive a coarse status + issues list.
        issues: list[str] = []
        status = "OK"

        if base_stats.get("spans", 0) == 0:
            status = "EMPTY"
            issues.append(
                "Index database is present but contains no spans. "
                "Did you run `rag index` for this repo?"
            )

        if orphan_enrichments:
            status = "WARN"
            issues.append(
                f"{orphan_enrichments} enrichment rows have no backing span "
                "(possible legacy data or manual DB edits)."
            )

        if pending_enrichments:
            if status == "OK":
                status = "WARN"
            issues.append(f"{pending_enrichments} spans are pending enrichment.")

        if pending_embeddings:
            if status == "OK":
                status = "WARN"
            issues.append(f"{pending_embeddings} spans are pending embeddings (profile 'default').")

        stats = {
            **base_stats,
            "pending_enrichments": int(pending_enrichments),
            "pending_embeddings": int(pending_embeddings),
            "orphan_enrichments": int(orphan_enrichments),
        }

        return {
            "status": status,
            "repo": str(repo_path),
            "db_path": str(db_path),
            "timestamp": now,
            "stats": stats,
            "top_pending_files": top_pending_files,
            "issues": issues,
        }
    finally:
        db.close()


def format_rag_doctor_summary(result: dict[str, Any], repo_name: str) -> str:
    """Format a single-line summary suitable for service logs."""
    status = result.get("status", "UNKNOWN")
    db_path = result.get("db_path")
    stats = result.get("stats")

    prefix = f"  🧪 RAG doctor ({repo_name}): "

    if status == "NO_DB":
        return prefix + f"no index database found (expected at {db_path})"

    if stats is None:
        return prefix + "unable to read stats (no data)"

    files = stats.get("files", 0)
    spans = stats.get("spans", 0)
    enrichments = stats.get("enrichments", 0)
    embeddings = stats.get("embeddings", 0)
    pending_enrichments = stats.get("pending_enrichments", 0)
    pending_embeddings = stats.get("pending_embeddings", 0)
    orphan_enrichments = stats.get("orphan_enrichments", 0)

    summary = (
        f"{prefix}files={files}, spans={spans}, "
        f"enrichments={enrichments} (pending={pending_enrichments}), "
        f"embeddings={embeddings} (pending={pending_embeddings}), "
        f"orphans={orphan_enrichments}"
    )

    issues = result.get("issues") or []
    if issues:
        summary += f" | first_issue: {issues[0]}"

    return summary


if __name__ == "__main__":
    # Manual testing utility: `python -m tools.rag.doctor /path/to/repo`
    import argparse
    import json
    import sys as _sys

    parser = argparse.ArgumentParser(description="Run RAG doctor diagnostics.")
    parser.add_argument("repo", type=Path, nargs="?", default=Path("."), help="Repository path")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show extra details in JSON output"
    )
    args = parser.parse_args()

    report = run_rag_doctor(args.repo, verbose=args.verbose)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    status = report.get("status", "OK")
    code = 0 if status in ("OK", "EMPTY") else 1
    _sys.exit(code)
