#!/usr/bin/env python3
"""
RAG Data Quality Validator

Validates enrichment data quality by checking for:
- Fake/placeholder summaries
- Empty or low-quality fields
- Schema violations
- Statistical anomalies

Usage:
    python3 scripts/rag_quality_check.py /path/to/repo
    python3 scripts/rag_quality_check.py /path/to/repo --json
    python3 scripts/rag_quality_check.py /path/to/repo --fix  # Auto-delete bad data
"""

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

# Add repo to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tools.rag.config import index_path_for_read


class QualityChecker:
    """Check RAG enrichment data quality."""
    
    # Known bad patterns
    FAKE_PATTERNS = [
        r"auto-summary generated offline",
        r"^[^:]+:\d+-\d+ auto-summary",
        r"TODO: implement",
        r"PLACEHOLDER",
    ]
    
    # Low quality indicators
    LOW_QUALITY_PATTERNS = [
        r"^(This|The) (code|function|method|class)",  # Generic starts
        r"^(undefined|unknown|N/A)",  # Missing data
        r"^\s*$",  # Empty
    ]
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
    def close(self):
        self.conn.close()
    
    def get_enrichment_stats(self) -> Dict[str, int]:
        """Get basic statistics."""
        cursor = self.conn.cursor()
        
        stats = {}
        
        # Total enrichments
        cursor.execute("SELECT COUNT(*) FROM enrichments")
        stats['total'] = cursor.fetchone()[0]
        
        # By model
        cursor.execute("""
            SELECT model, COUNT(*) as count
            FROM enrichments
            GROUP BY model
        """)
        stats['by_model'] = {row['model']: row['count'] for row in cursor.fetchall()}
        
        # Recent (last 24h)
        cursor.execute("""
            SELECT COUNT(*) FROM enrichments
            WHERE created_at > datetime('now', '-1 day')
        """)
        stats['recent_24h'] = cursor.fetchone()[0]
        
        return stats
    
    def check_fake_data(self) -> List[Dict]:
        """Find fake/placeholder enrichments."""
        cursor = self.conn.cursor()
        fake_entries = []
        
        # Check for exact known bad strings using LIKE (REGEXP not available in standard SQLite)
        cursor.execute("""
            SELECT span_hash, summary, model, created_at
            FROM enrichments
            WHERE summary LIKE '%auto-summary generated offline%'
               OR summary LIKE '%TODO: implement%'
               OR summary LIKE '%PLACEHOLDER%'
        """)
        
        for row in cursor.fetchall():
            fake_entries.append({
                'span_hash': row['span_hash'],
                'summary': row['summary'][:100],
                'model': row['model'],
                'created_at': row['created_at'],
                'reason': 'Known fake placeholder text'
            })
        
        return fake_entries
    
    def check_empty_fields(self) -> List[Dict]:
        """Find enrichments with missing/empty critical fields."""
        cursor = self.conn.cursor()
        problems = []
        
        # Empty or very short summaries
        cursor.execute("""
            SELECT span_hash, summary, model
            FROM enrichments
            WHERE LENGTH(TRIM(summary)) < 10
        """)
        
        for row in cursor.fetchall():
            problems.append({
                'span_hash': row['span_hash'],
                'issue': 'Summary too short (< 10 chars)',
                'model': row['model']
            })
        
        # No inputs/outputs (might be ok for some code, but suspicious)
        cursor.execute("""
            SELECT span_hash, inputs, outputs, model
            FROM enrichments
            WHERE inputs = '[]' AND outputs = '[]'
        """)
        
        for row in cursor.fetchall():
            problems.append({
                'span_hash': row['span_hash'],
                'issue': 'Both inputs and outputs empty',
                'model': row['model']
            })
        
        return problems
    
    def check_low_quality_summaries(self) -> List[Dict]:
        """Find suspiciously low-quality summaries."""
        cursor = self.conn.cursor()
        low_quality = []
        
        cursor.execute("""
            SELECT span_hash, summary, model
            FROM enrichments
        """)
        
        for row in cursor.fetchall():
            summary = row['summary']
            
            # Check for generic patterns
            for pattern in self.LOW_QUALITY_PATTERNS:
                if re.search(pattern, summary, re.IGNORECASE):
                    low_quality.append({
                        'span_hash': row['span_hash'],
                        'summary': summary[:100],
                        'model': row['model'],
                        'reason': f'Generic/low-quality pattern: {pattern}'
                    })
                    break
            
            # Check word count
            word_count = len(summary.split())
            if word_count < 5:
                low_quality.append({
                    'span_hash': row['span_hash'],
                    'summary': summary[:100],
                    'model': row['model'],
                    'reason': f'Too few words: {word_count}'
                })
        
        return low_quality
    
    def check_model_distribution(self) -> Dict:
        """Check if enrichments are using expected models."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT model, COUNT(*) as count
            FROM enrichments
            GROUP BY model
        """)
        
        distribution = {}
        for row in cursor.fetchall():
            distribution[row['model']] = row['count']
        
        # Flag suspicious models
        warnings = []
        for model, count in distribution.items():
            if model in ['unknown', 'default', 'placeholder']:
                warnings.append(f"Suspicious model name: {model} ({count} enrichments)")
        
        return {
            'distribution': distribution,
            'warnings': warnings
        }
    
    def delete_fake_data(self) -> int:
        """Delete all identified fake/placeholder data."""
        cursor = self.conn.cursor()
        
        # Delete by LIKE patterns (REGEXP not available in standard SQLite)
        cursor.execute("""
            DELETE FROM enrichments
            WHERE summary LIKE '%auto-summary generated offline%'
               OR summary LIKE '%TODO: implement%'
               OR summary LIKE '%PLACEHOLDER%'
        """)
        deleted = cursor.rowcount
        
        self.conn.commit()
        return deleted
    
    def generate_report(self) -> Dict:
        """Generate comprehensive quality report."""
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'database': str(self.db_path),
            'stats': self.get_enrichment_stats(),
            'fake_data': self.check_fake_data(),
            'empty_fields': self.check_empty_fields(),
            'low_quality': self.check_low_quality_summaries(),
            'model_dist': self.check_model_distribution(),
        }
        
        # Calculate quality score
        total = report['stats']['total']
        if total > 0:
            problems = (
                len(report['fake_data']) +
                len(report['empty_fields']) +
                len(report['low_quality'])
            )
            report['quality_score'] = max(0, 100 - (problems / total * 100))
        else:
            report['quality_score'] = 0
        
        # Pass/fail
        report['status'] = 'PASS' if report['quality_score'] >= 90 else 'FAIL'
        
        return report


def print_report(report: Dict, verbose: bool = True):
    """Print human-readable report."""
    print("=" * 70)
    print("RAG DATA QUALITY REPORT")
    print("=" * 70)
    print()
    
    stats = report['stats']
    print(f"📊 Statistics:")
    print(f"  Total enrichments: {stats['total']}")
    print(f"  Recent (24h): {stats['recent_24h']}")
    print()
    
    print(f"🎯 Quality Score: {report['quality_score']:.1f}/100 - {report['status']}")
    print()
    
    # Model distribution
    model_dist = report['model_dist']
    print(f"🤖 Model Distribution:")
    for model, count in model_dist['distribution'].items():
        pct = (count / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"  {model}: {count} ({pct:.1f}%)")
    
    if model_dist['warnings']:
        print(f"  ⚠️  Warnings:")
        for warning in model_dist['warnings']:
            print(f"    - {warning}")
    print()
    
    # Issues
    fake_count = len(report['fake_data'])
    empty_count = len(report['empty_fields'])
    low_q_count = len(report['low_quality'])
    
    print(f"🚨 Issues Found:")
    print(f"  Fake/placeholder data: {fake_count}")
    print(f"  Empty/missing fields: {empty_count}")
    print(f"  Low-quality summaries: {low_q_count}")
    print()
    
    if verbose and (fake_count > 0 or empty_count > 0 or low_q_count > 0):
        if fake_count > 0:
            print("❌ Fake Data Examples:")
            for entry in report['fake_data'][:5]:
                print(f"  - {entry['span_hash'][:12]}... | {entry['summary'][:60]}...")
                print(f"    Model: {entry['model']} | Reason: {entry['reason']}")
            if fake_count > 5:
                print(f"  ... and {fake_count - 5} more")
            print()
        
        if empty_count > 0:
            print("⚠️  Empty Fields Examples:")
            for entry in report['empty_fields'][:5]:
                print(f"  - {entry['span_hash'][:12]}... | {entry['issue']}")
            if empty_count > 5:
                print(f"  ... and {empty_count - 5} more")
            print()
        
        if low_q_count > 0:
            print("📉 Low Quality Examples:")
            for entry in report['low_quality'][:5]:
                print(f"  - {entry['span_hash'][:12]}... | {entry['summary'][:60]}...")
                print(f"    Reason: {entry['reason']}")
            if low_q_count > 5:
                print(f"  ... and {low_q_count - 5} more")
            print()
    
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Check RAG enrichment data quality")
    parser.add_argument("repo", type=Path, help="Repository path")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    parser.add_argument("--fix", action="store_true", help="Delete identified fake data")
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
            print("🔧 Deleting fake/placeholder data...")
            deleted = checker.delete_fake_data()
            print(f"✅ Deleted {deleted} fake enrichments")
            print()
            
            # Re-generate report after deletion
            report = checker.generate_report()
        
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print_report(report, verbose=not args.quiet)
        
        # Exit code based on quality
        return 0 if report['status'] == 'PASS' else 1
    
    finally:
        checker.close()


if __name__ == "__main__":
    sys.exit(main())
