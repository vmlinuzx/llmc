#!/usr/bin/env python3
"""
repair_orphan_files.py - Fix files that have 0 spans due to extractor failures.

This script:
1. Finds all files in the DB with 0 spans
2. Forces a reindex by touching the file hash
3. Triggers the indexer to re-extract spans

Usage:
    python scripts/repair_orphan_files.py [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from llmc.rag.config import index_path_for_write
from llmc.rag.database import Database
from llmc.rag.utils import find_repo_root
from llmc.rag.indexer import sync_paths


def find_orphan_files(db: Database) -> list[str]:
    """Find all files with 0 spans."""
    rows = db.conn.execute("""
        SELECT f.path
        FROM files f
        WHERE NOT EXISTS (SELECT 1 FROM spans s WHERE s.file_id = f.id)
        ORDER BY f.path
    """).fetchall()
    return [row[0] for row in rows]


def invalidate_file_hash(db: Database, path: str) -> None:
    """Invalidate a file's hash so it gets reindexed."""
    db.conn.execute(
        "UPDATE files SET file_hash = 'INVALIDATED_FOR_REINDEX' WHERE path = ?",
        (path,)
    )


def main():
    parser = argparse.ArgumentParser(description="Repair orphan files with 0 spans")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of files to repair (0 = all)")
    args = parser.parse_args()

    repo_root = find_repo_root()
    db_path = index_path_for_write(repo_root)
    db = Database(db_path)

    orphans = find_orphan_files(db)
    
    if not orphans:
        print("✅ No orphan files found - all files have spans!")
        return 0
    
    print(f"Found {len(orphans)} orphan files with 0 spans:")
    for path in orphans[:20]:
        print(f"  - {path}")
    if len(orphans) > 20:
        print(f"  ... and {len(orphans) - 20} more")
    print()
    
    if args.limit:
        orphans = orphans[:args.limit]
        print(f"Limiting to first {args.limit} files")
    
    if args.dry_run:
        print("DRY RUN - no changes made")
        return 0
    
    # Invalidate file hashes
    print(f"\n📝 Invalidating file hashes for {len(orphans)} files...")
    for path in orphans:
        invalidate_file_hash(db, path)
    db.conn.commit()
    
    # Trigger sync_paths to reindex
    print(f"\n🔄 Triggering reindex for {len(orphans)} files...")
    paths = [Path(p) for p in orphans]
    stats = sync_paths(paths)
    
    print(f"\n✅ Repair complete!")
    print(f"   Files processed: {stats.files}")
    print(f"   Spans created: {stats.spans}")
    print(f"   Duration: {stats.get('duration_sec', 0):.2f}s")
    
    # Verify repair
    remaining = find_orphan_files(db)
    if remaining:
        print(f"\n⚠️  {len(remaining)} files still have 0 spans (may be empty/unsupported)")
        for path in remaining[:10]:
            print(f"    - {path}")
    else:
        print("\n🎉 All files now have spans!")
    
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
