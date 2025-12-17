#!/usr/bin/env python3
"""
Add quality checking to RAG service

This module extends the RAG service to periodically validate data quality.
Uses canonical language-aware classifier (v1-cjk-aware) for consistent results.
"""

from datetime import UTC
from pathlib import Path
import sys

from llmc.rag.config import index_path_for_read


def run_quality_check(repo_path: Path, verbose: bool = False) -> dict:
    """
    Run quality check on a repo's RAG database using canonical classifier.

    Uses language-aware rules (v1-cjk-aware):
    - PLACEHOLDER: Known fake/boilerplate patterns
    - EMPTY: Only whitespace/punctuation
    - SHORT: Too terse for language/length
    - OK: Contentful and acceptable

    Returns a dict with:
        - quality_score: float (0-100)
        - status: 'PASS' or 'FAIL'
        - placeholder_count: int
        - empty_count: int
        - short_count: int
        - ok_count: int
        - total: int
        - rule_version: str
        - checked_at: str
    """
    from datetime import datetime
    import sqlite3

    # Import classifier here to avoid circular import with types.py
    from llmc.rag.quality_check import RULE_VERSION, classify_quality

    db_path = index_path_for_read(repo_path)
    if not db_path.exists():
        return {
            "quality_score": 0,
            "status": "NO_DB",
            "placeholder_count": 0,
            "empty_count": 0,
            "short_count": 0,
            "ok_count": 0,
            "total": 0,
            "rule_version": RULE_VERSION,
            "checked_at": datetime.now(UTC).isoformat(),
        }

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Get total count
        cursor.execute("SELECT COUNT(*) as total FROM enrichments")
        total = cursor.fetchone()["total"]

        if total == 0:
            return {
                "quality_score": 0,
                "status": "EMPTY",
                "placeholder_count": 0,
                "empty_count": 0,
                "short_count": 0,
                "ok_count": 0,
                "total": 0,
                "rule_version": RULE_VERSION,
                "checked_at": datetime.now(UTC).isoformat(),
            }

        # Use canonical classifier for each enrichment
        # Count distinct rows per classification (no overlap)
        placeholder_count = 0
        empty_count = 0
        short_count = 0
        ok_count = 0

        # Fetch all summaries to classify
        cursor.execute("SELECT span_hash, summary FROM enrichments")

        for row in cursor.fetchall():
            quality_result = classify_quality(row["summary"])

            if quality_result.classification == "PLACEHOLDER":
                placeholder_count += 1
            elif quality_result.classification == "EMPTY":
                empty_count += 1
            elif quality_result.classification == "SHORT":
                short_count += 1
            elif quality_result.classification == "OK":
                ok_count += 1

        # Calculate quality score (OK / total)
        quality_score = (ok_count / total * 100) if total > 0 else 0

        result = {
            "quality_score": quality_score,
            "status": "PASS" if quality_score >= 90 else "FAIL",
            "placeholder_count": placeholder_count,
            "empty_count": empty_count,
            "short_count": short_count,
            "ok_count": ok_count,
            "total": total,
            "rule_version": RULE_VERSION,
            "checked_at": datetime.now(UTC).isoformat(),
        }

        return result

    finally:
        conn.close()


def format_quality_summary(result: dict, repo_name: str) -> str:
    """Format quality check result for console output."""
    if result["status"] == "NO_DB":
        return f"  ℹ️  {repo_name}: No RAG database yet"

    if result["status"] == "EMPTY":
        return f"  ℹ️  {repo_name}: Database empty (no enrichments)"

    score = result["quality_score"]
    total = result["total"]
    placeholder = result["placeholder_count"]
    empty = result["empty_count"]
    short = result["short_count"]
    result["ok_count"]

    if result["status"] == "PASS":
        emoji = "✅"
    else:
        emoji = "⚠️"

    summary = f"  {emoji} {repo_name}: Quality {score:.1f}% ({total} enrichments"

    issues = []
    if placeholder > 0:
        issues.append(f"{placeholder} placeholder")
    if empty > 0:
        issues.append(f"{empty} empty")
    if short > 0:
        issues.append(f"{short} short")

    if issues:
        summary += f", issues: {', '.join(issues)}"

    summary += f") [{result['rule_version']}]"
    return summary


if __name__ == "__main__":
    # Can be used standalone for testing
    import argparse

    parser = argparse.ArgumentParser(description="Run quality check")
    parser.add_argument("repo", type=Path, help="Repository path")
    args = parser.parse_args()

    result = run_quality_check(args.repo)
    print(format_quality_summary(result, args.repo.name))

    sys.exit(0 if result["status"] == "PASS" else 1)
