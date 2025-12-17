#!/usr/bin/env python3
"""
Migration script: Rebuild FTS5 index without stopwords

ISSUE: P0 Critical - "model" keyword filtered by FTS5 default stopwords
FIX: Rebuild enrichments_fts table with unicode61 tokenizer (no stopwords)

Usage:
    python scripts/migrate_fts5_no_stopwords.py [repo_root]

This script:
1. Drops the existing enrichments_fts table
2. Recreates it with unicode61 tokenizer (no stopwords)
3. Rebuilds the FTS index from enrichments data
"""

from pathlib import Path
import sys

# Add repo root to path
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

from llmc.rag.config import index_path_for_read
from llmc.rag.database import Database


def migrate_fts5_index(repo_root: Path) -> None:
    """Rebuild FTS5 index without stopwords for a single repository."""
    try:
        db_path = index_path_for_read(repo_root)
    except FileNotFoundError:
        print(f"⚠️  No RAG database found for {repo_root}")
        return

    print(f"📂 Migrating FTS5 index: {db_path}")
    
    db = Database(db_path)
    try:
        # Drop existing FTS table
        print("  🗑️  Dropping old enrichments_fts table...")
        db.conn.execute("DROP TABLE IF EXISTS enrichments_fts")
        
        # Recreate with unicode61 tokenizer (no stopwords)
        print("  ✨ Creating new enrichments_fts table (unicode61, no stopwords)...")
        db.conn.execute(
            """
            CREATE VIRTUAL TABLE enrichments_fts
            USING fts5(
                symbol,
                summary,
                path,
                start_line,
                end_line,
                tokenize='unicode61'
            )
            """
        )
        
        # Rebuild index
        print("  📊 Rebuilding FTS index from enrichment data...")
        count = db.rebuild_enrichments_fts()
        
        # Commit
        db.conn.commit()
        
        print(f"  ✅ Migration complete! Indexed {count} enrichments")
        print("  🎯 Keyword 'model' is now searchable!")
        
    except Exception as e:
        print(f"  ❌ Migration failed: {e}")
        raise
    finally:
        db.close()


def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1:
        repo_root = Path(sys.argv[1]).resolve()
    else:
        # Default to current directory
        repo_root = Path.cwd()
        # Walk up to find .git directory
        while not (repo_root / ".git").exists() and repo_root != repo_root.parent:
            repo_root = repo_root.parent
    
    print("=" * 70)
    print("FTS5 STOPWORDS MIGRATION")
    print("=" * 70)
    print()
    
    if not repo_root.exists():
        print(f"❌ Repository not found: {repo_root}")
        sys.exit(1)
    
    migrate_fts5_index(repo_root)
    
    print()
    print("=" * 70)
    print("MIGRATION COMPLETE")
    print("=" * 70)
    print()
    print("💡 TIP: Test the fix with:")
    print(f"   cd {repo_root}")
    print('   llmc-cli rag search "model routing"')
    print()


if __name__ == "__main__":
    main()
