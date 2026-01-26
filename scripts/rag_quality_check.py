#!/usr/bin/env python3
"""
RAG Data Quality Validator (v1-cjk-aware)

Validates enrichment data quality using canonical language-aware classifier.
Replaces broken space-counting with CJK/English-aware heuristics.

Usage:
    python3 scripts/rag_quality_check.py /path/to/repo
    python3 scripts/rag_quality_check.py /path/to/repo --json
    python3 scripts/rag_quality_check.py /path/to/repo --fix  # Auto-delete bad data
"""

import argparse
import json
import sqlite3
import sys

try:
except ImportError:
    pass
from datetime import UTC, datetime
from pathlib import Path

from llmc.rag.config import index_path_for_read
from llmc.rag.quality_check import RULE_VERSION, classify_quality


class QualityChecker:
    """Check RAG enrichment data quality using canonical classifier."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        self.conn.close()

    def get_enrichment_stats(self) -> dict:
        """Get basic statistics."""
        cursor = self.conn.cursor()

        stats = {}

        # Total enrichments
        cursor.execute("SELECT COUNT(*) FROM enrichments")
        stats["total"] = cursor.fetchone()[0]

        # By model
        cursor.execute(
            """
            SELECT model, COUNT(*) as count
            FROM enrichments
            GROUP BY model
        """
        )
        stats["by_model"] = {row["model"]: row["count"] for row in cursor.fetchall()}

        # Recent (last 24h)
        cursor.execute(
            """
            SELECT COUNT(*) FROM enrichments
            WHERE created_at > datetime('now', '-1 day')
        """
        )
        stats["recent_24h"] = cursor.fetchone()[0]

        return stats

    def check_all_issues(self) -> dict[str, list]:
        """Check for all quality issues using canonical classifier."""
        cursor = self.conn.cursor()

        issues = {"placeholders": [], "empty": [], "short": [], "ok": []}

        # Fetch all enrichments
        cursor.execute("SELECT span_hash, summary, model, created_at FROM enrichments")

        for row in cursor.fetchall():
            result = classify_quality(row["summary"])

            entry = {
                "span_hash": row["span_hash"],
                "summary": row["summary"][:100],
                "model": row["model"],
                "created_at": row["created_at"],
                "reason": result.reason,
            }

            if result.classification == "PLACEHOLDER":
                issues["placeholders"].append(entry)
            elif result.classification == "EMPTY":
                issues["empty"].append(entry)
            elif result.classification == "SHORT":
                issues["short"].append(entry)
            elif result.classification == "OK":
                issues["ok"].append(entry)

        return issues

    def delete_placeholder_data(self) -> int:
        """Delete all identified placeholder/fake data."""
        cursor = self.conn.cursor()

        cursor.execute(
            """
            DELETE FROM enrichments
            WHERE summary LIKE '%auto-summary generated offline%'
               OR summary LIKE '%TODO: implement%'
               OR summary LIKE '%PLACEHOLDER%'
               OR summary LIKE '%fake%'
               OR summary GLOB '*-*-*-*'
               OR summary GLOB '*auto-summary*'
        """
        )
        deleted = cursor.rowcount

        self.conn.commit()
        return deleted

    def generate_report(self) -> dict:
        """Generate comprehensive quality report."""
        stats = self.get_enrichment_stats()
        issues = self.check_all_issues()

        total = stats["total"]
        placeholders = len(issues["placeholders"])
        empty = len(issues["empty"])
        short = len(issues["short"])
        ok = len(issues["ok"])

        # Calculate quality score (OK / total)
        quality_score = (ok / total * 100) if total > 0 else 0

        report = {
            "timestamp": datetime.now(UTC).isoformat(),
            "database": str(self.db_path),
            "rule_version": RULE_VERSION,
            "stats": stats,
            "issues": {
                "placeholder_count": placeholders,
                "empty_count": empty,
                "short_count": short,
                "ok_count": ok,
            },
            "quality_score": quality_score,
            "status": "PASS" if quality_score >= 90 else "FAIL",
        }

        return report


def print_report(report: dict, verbose: bool = True):
    """Print human-readable report."""
    print("=" * 70)
    print("RAG DATA QUALITY REPORT")
    print(f"Rule Version: {report['rule_version']}")
    print("=" * 70)
    print()

    stats = report["stats"]
    print("📊 Statistics:")
    print(f"  Total enrichments: {stats['total']}")
    print(f"  Recent (24h): {stats['recent_24h']}")
    print()

    print(f"🎯 Quality Score: {report['quality_score']:.1f}/100 - {report['status']}")
    print()

    # Model distribution
    print("🤖 Model Distribution:")
    for model, count in stats["by_model"].items():
        pct = (count / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"  {model}: {count} ({pct:.1f}%)")
    print()

    # Issues
    placeholder = report["issues"]["placeholder_count"]
    empty = report["issues"]["empty_count"]
    short = report["issues"]["short_count"]

    print("🚨 Issues Found:")
    print(f"  Placeholder/fake data: {placeholder}")
    print(f"  Empty fields: {empty}")
    print(f"  Short summaries: {short}")
    print()

    if verbose and (placeholder > 0 or empty > 0 or short > 0):
        if placeholder > 0:
            print("❌ Placeholder Examples:")
            for entry in report["issues"]["placeholders"][:5]:
                print(f"  - {entry['span_hash'][:12]}... | {entry['summary'][:60]}...")
                print(f"    Reason: {entry['reason']}")
            if placeholder > 5:
                print(f"  ... and {placeholder - 5} more")
            print()

        if empty > 0:
            print("⚠️  Empty Examples:")
            for entry in report["issues"]["empty"][:5]:
                print(f"  - {entry['span_hash'][:12]}... | {entry['reason']}")
            if empty > 5:
                print(f"  ... and {empty - 5} more")
            print()

        if short > 0:
            print("📉 Short Examples:")
            for entry in report["issues"]["short"][:5]:
                print(f"  - {entry['span_hash'][:12]}... | {entry['summary'][:60]}...")
                print(f"    Reason: {entry['reason']}")
            if short > 5:
                print(f"  ... and {short - 5} more")
            print()

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Check RAG enrichment data quality (v1-cjk-aware)"
    )
    parser.add_argument("repo", type=Path, help="Repository path")
    parser.add_argument(
        "--json", action="store_true", help="Output JSON instead of human-readable"
    )
    parser.add_argument(
        "--fix", action="store_true", help="Delete identified placeholder data"
    )
    parser.add_argument("--quiet", action="store_true", help="Only show summary")

    args = parser.parse_args()

    repo = args.repo.resolve()
    if not repo.exists():
        print(f"Error: Repository not found: {repo}", file=sys.stderr)
        return 1

    db_path = index_path_for_read(repo)
    if not db_path.exists():
        print(f"Error: No RAG database found at: {db_path}", file=sys.stderr)
        return 1

    checker = QualityChecker(db_path)

    try:
        report = checker.generate_report()

        if args.fix:
            print("🔧 Deleting placeholder/fake data...")
            deleted = checker.delete_placeholder_data()
            print(f"✅ Deleted {deleted} placeholder enrichments")
            print()

            # Re-generate report after deletion
            report = checker.generate_report()

        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_report(report, verbose=not args.quiet)

        # Exit code based on quality
        return 0 if report["status"] == "PASS" else 1

    finally:
        checker.close()


if __name__ == "__main__":
    sys.exit(main())
