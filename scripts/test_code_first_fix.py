#!/usr/bin/env python3
"""
Quick test to verify code-first prioritization is working after the fix.

This script:
1. Fetches pending enrichments from the database
2. Checks the file type distribution
3. Verifies we're getting a mix of .py and .md files, not all .md files

Usage:
    python scripts/test_code_first_fix.py
"""

from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.rag.database import Database


def test_pending_enrichments_diversity():
    """Test that pending_enrichments returns a diverse sample."""
    db_path = project_root / ".rag" / "index_v2.db"
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False
    
    db = Database(db_path)
    
    # Fetch 50 pending enrichments
    items = db.pending_enrichments(limit=50, cooldown_seconds=0)
    
    if not items:
        print("✓ No pending enrichments found")
        return True
    
    # Count file types
    py_files = 0
    md_files = 0
    other_files = 0
    
    files_seen = set()
    
    for item in items:
        path_str = str(item.file_path)
        files_seen.add(path_str)
        
        if path_str.endswith('.py'):
            py_files += 1
        elif path_str.endswith('.md'):
            md_files += 1
        else:
            other_files += 1
    
    total = len(items)
    
    print(f"\n📊 Pending Enrichments Sample (n={total}):")
    print(f"   .py files:    {py_files:3d} ({py_files/total*100:5.1f}%)")
    print(f"   .md files:    {md_files:3d} ({md_files/total*100:5.1f}%)")
    print(f"   other files:  {other_files:3d} ({other_files/total*100:5.1f}%)")
    print(f"\n   Unique files: {len(files_seen)}")
    
    # Show first 10 files
    print(f"\n📁 First 10 files in sample:")
    for i, item in enumerate(items[:10], 1):
        print(f"   {i:2d}. {item.file_path} (type={item.slice_type})")
    
    # Check for the bug: all files from same 1-2 markdown files
    if total >= 10:
        if len(files_seen) <= 2 and md_files == total:
            print(f"\n❌ BUG STILL PRESENT: All {total} items are from {len(files_seen)} markdown file(s)")
            print("   Expected: Mix of .py and .md files")
            return False
    
    # Check for good diversity
    if total >= 20:
        if len(files_seen) >= 10:
            print(f"\n✓ GOOD DIVERSITY: {len(files_seen)} unique files in sample of {total}")
        else:
            print(f"\n⚠️  LOW DIVERSITY: Only {len(files_seen)} unique files in sample of {total}")
            print("   This might be okay if there aren't many pending files")
    
    # Check for reasonable .py/.md ratio (should favor .py files)
    if py_files > 0 and md_files > 0:
        ratio = py_files / md_files
        print(f"\n   .py/.md ratio: {ratio:.2f}:1")
        if ratio >= 2.0:
            print("   ✓ Good ratio (favoring code files)")
        elif ratio >= 1.0:
            print("   ⚠️  Acceptable ratio (slight code preference)")
        else:
            print("   ⚠️  Low ratio (not favoring code files as expected)")
    
    return True


if __name__ == "__main__":
    success = test_pending_enrichments_diversity()
    sys.exit(0 if success else 1)
