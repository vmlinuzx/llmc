#!/usr/bin/env python3
"""
Migration: Add performance metrics columns to enrichments table.

This migration adds columns to track Ollama/LLM inference performance:
- tokens_per_second: Output generation speed (eval_count / eval_duration)
- eval_count: Number of output tokens generated
- eval_duration_ns: Time to generate output (nanoseconds)
- prompt_eval_count: Number of input tokens processed
- total_duration_ns: Total request time (nanoseconds)
- backend_host: Which server handled this enrichment

This data enables:
1. Performance comparison between models (e.g., Qwen 3B vs 7B)
2. Identifying slow backends or degraded performance
3. Cost estimation (token counts → API pricing)
4. Tracking GPU vs CPU inference speeds
5. Diagnosing ROCm vs Vulkan driver performance differences

Usage:
    python scripts/migrate_add_enrichment_metrics.py /path/to/repo
    python scripts/migrate_add_enrichment_metrics.py  # using cwd
"""

import sqlite3
import sys
from pathlib import Path


COLUMNS_TO_ADD = [
    ("tokens_per_second", "REAL"),
    ("eval_count", "INTEGER"),
    ("eval_duration_ns", "INTEGER"),
    ("prompt_eval_count", "INTEGER"),
    ("total_duration_ns", "INTEGER"),
    ("backend_host", "TEXT"),
]


def migrate_database(db_path: Path) -> None:
    """Add metrics columns to enrichments table."""
    print(f"Migrating: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Check existing columns
    cur.execute("PRAGMA table_info(enrichments)")
    existing = {row[1] for row in cur.fetchall()}
    print(f"  Existing columns: {len(existing)}")
    
    added = 0
    for col_name, col_type in COLUMNS_TO_ADD:
        if col_name in existing:
            print(f"  ✓ {col_name} already exists")
        else:
            try:
                cur.execute(f"ALTER TABLE enrichments ADD COLUMN {col_name} {col_type}")
                print(f"  + Added {col_name} ({col_type})")
                added += 1
            except sqlite3.OperationalError as e:
                print(f"  ✗ Failed to add {col_name}: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"Migration complete: {added} columns added")


def find_rag_database(repo_path: Path) -> Path | None:
    """Find the RAG database in a repo."""
    # Try standard locations
    candidates = [
        repo_path / ".rag" / "index_v2.db",
        repo_path / ".llmc" / "rag" / "index.db",
        repo_path / ".llmc" / "index_v2.db",
    ]
    
    for candidate in candidates:
        if candidate.exists():
            return candidate
    
    return None


def main():
    # Parse args
    if len(sys.argv) > 1:
        repo_path = Path(sys.argv[1]).resolve()
    else:
        repo_path = Path.cwd()
    
    if not repo_path.exists():
        print(f"Error: Path does not exist: {repo_path}")
        sys.exit(1)
    
    # Handle direct DB path
    if repo_path.suffix == ".db":
        migrate_database(repo_path)
        return
    
    # Find database
    db_path = find_rag_database(repo_path)
    if not db_path:
        print(f"Error: Could not find RAG database in {repo_path}")
        print("Searched: .rag/index_v2.db, .llmc/rag/index.db, .llmc/index_v2.db")
        sys.exit(1)
    
    migrate_database(db_path)


if __name__ == "__main__":
    main()
