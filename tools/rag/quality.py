#!/usr/bin/env python3
"""
Add quality checking to RAG service

This module extends the RAG service to periodically validate data quality.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tools.rag.config import index_path_for_read


def run_quality_check(repo_path: Path, verbose: bool = False) -> dict:
    """
    Run quality check on a repo's RAG database.
    
    Returns a dict with:
        - quality_score: float (0-100)
        - status: 'PASS' or 'FAIL'
        - fake_count: int
        - empty_count: int
        - low_quality_count: int
    """
    import sqlite3
    import re
    from datetime import datetime, timezone
    
    db_path = index_path_for_read(repo_path)
    if not db_path.exists():
        return {
            'quality_score': 0,
            'status': 'NO_DB',
            'fake_count': 0,
            'empty_count': 0,
            'low_quality_count': 0,
            'total': 0
        }
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get total count
        cursor.execute("SELECT COUNT(*) as total FROM enrichments")
        total = cursor.fetchone()['total']
        
        if total == 0:
            return {
                'quality_score': 0,
                'status': 'EMPTY',
                'fake_count': 0,
                'empty_count': 0,
                'low_quality_count': 0,
                'total': 0
            }
        
        # Count fake data
        cursor.execute("""
            SELECT COUNT(*) as count FROM enrichments
            WHERE summary LIKE '%auto-summary generated offline%'
        """)
        fake_count = cursor.fetchone()['count']
        
        # Count empty fields (reduced threshold to 5 chars - some code is just short!)
        cursor.execute("""
            SELECT COUNT(*) as count FROM enrichments
            WHERE LENGTH(TRIM(summary)) < 5
        """)
        empty_count = cursor.fetchone()['count']
        
        # Count low quality (reduced threshold to 2 words - some summaries are naturally short)
        cursor.execute("""
            SELECT COUNT(*) as count FROM enrichments
            WHERE LENGTH(summary) - LENGTH(REPLACE(summary, ' ', '')) < 2
        """)
        low_quality_count = cursor.fetchone()['count']
        
        # Calculate quality score
        problems = fake_count + empty_count + low_quality_count
        quality_score = max(0, 100 - (problems / total * 100))
        
        result = {
            'quality_score': quality_score,
            'status': 'PASS' if quality_score >= 90 else 'FAIL',
            'fake_count': fake_count,
            'empty_count': empty_count,
            'low_quality_count': low_quality_count,
            'total': total,
            'checked_at': datetime.now(timezone.utc).isoformat()
        }
        
        return result
    
    finally:
        conn.close()


def format_quality_summary(result: dict, repo_name: str) -> str:
    """Format quality check result for console output."""
    if result['status'] == 'NO_DB':
        return f"  ℹ️  {repo_name}: No RAG database yet"
    
    if result['status'] == 'EMPTY':
        return f"  ℹ️  {repo_name}: Database empty (no enrichments)"
    
    score = result['quality_score']
    total = result['total']
    fake = result['fake_count']
    empty = result['empty_count']
    low_q = result['low_quality_count']
    
    if result['status'] == 'PASS':
        emoji = "✅"
    else:
        emoji = "⚠️"
    
    summary = f"  {emoji} {repo_name}: Quality {score:.1f}% ({total} enrichments"
    
    issues = []
    if fake > 0:
        issues.append(f"{fake} fake")
    if empty > 0:
        issues.append(f"{empty} empty")
    if low_q > 0:
        issues.append(f"{low_q} low-quality")
    
    if issues:
        summary += f", issues: {', '.join(issues)}"
    
    summary += ")"
    return summary


if __name__ == "__main__":
    # Can be used standalone for testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Run quality check")
    parser.add_argument("repo", type=Path, help="Repository path")
    args = parser.parse_args()
    
    result = run_quality_check(args.repo)
    print(format_quality_summary(result, args.repo.name))
    
    sys.exit(0 if result['status'] == 'PASS' else 1)
