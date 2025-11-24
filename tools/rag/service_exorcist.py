"""
Exorcist command: Nuclear database rebuild.

Sometimes you need to burn it down and start fresh.
If there's a spider in there, nukes from orbit are the only way to be sure.
"""
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Dict


class ExorcistStats:
    """Statistics about what will be deleted."""
    
    def __init__(self, repo: Path):
        self.repo = repo
        self.rag_dir = repo / ".rag"
        
        self.index_db = self.rag_dir / "rag_index.db"
        self.enrichments = self.rag_dir / "enrichments.json"
        self.embeddings_db = self.rag_dir / "embeddings.db"
        self.quality_dir = self.rag_dir / "quality_reports"
        self.failures_db = self.rag_dir / "failures.db"
    
    def gather(self) -> Dict:
        """Gather statistics about what exists."""
        stats = {
            "exists": self.rag_dir.exists(),
            "files": [],
            "total_size_bytes": 0,
            "span_count": 0,
            "enrichment_count": 0,
            "embedding_count": 0,
        }
        
        if not stats["exists"]:
            return stats
        
        # Index database
        if self.index_db.exists():
            size = self.index_db.stat().st_size
            stats["files"].append({
                "path": str(self.index_db.relative_to(self.repo)),
                "size_bytes": size
            })
            stats["total_size_bytes"] += size
            
            # Count spans in index
            try:
                conn = sqlite3.connect(self.index_db)
                cursor = conn.execute("SELECT COUNT(*) FROM spans")
                stats["span_count"] = cursor.fetchone()[0]
                conn.close()
            except Exception:
                pass
        
        # Enrichments JSON
        if self.enrichments.exists():
            size = self.enrichments.stat().st_size
            stats["files"].append({
                "path": str(self.enrichments.relative_to(self.repo)),
                "size_bytes": size
            })
            stats["total_size_bytes"] += size
            
            # Count enrichments
            try:
                data = json.loads(self.enrichments.read_text())
                stats["enrichment_count"] = len(data)
            except Exception:
                pass
        
        # Embeddings database
        if self.embeddings_db.exists():
            size = self.embeddings_db.stat().st_size
            stats["files"].append({
                "path": str(self.embeddings_db.relative_to(self.repo)),
                "size_bytes": size
            })
            stats["total_size_bytes"] += size
            
            # Count embeddings
            try:
                conn = sqlite3.connect(self.embeddings_db)
                cursor = conn.execute("SELECT COUNT(*) FROM embeddings")
                stats["embedding_count"] = cursor.fetchone()[0]
                conn.close()
            except Exception:
                pass
        
        # Quality reports
        if self.quality_dir.exists():
            for file in self.quality_dir.rglob("*"):
                if file.is_file():
                    size = file.stat().st_size
                    stats["files"].append({
                        "path": str(file.relative_to(self.repo)),
                        "size_bytes": size
                    })
                    stats["total_size_bytes"] += size
        
        # Failures database
        if self.failures_db.exists():
            size = self.failures_db.stat().st_size
            stats["files"].append({
                "path": str(self.failures_db.relative_to(self.repo)),
                "size_bytes": size
            })
            stats["total_size_bytes"] += size
        
        return stats


class Exorcist:
    """Handles nuclear database rebuild with DC's personality."""
    
    def __init__(self, repo: Path):
        self.repo = repo
        self.stats = ExorcistStats(repo)
    
    def print_warning(self, stats: Dict):
        """Print DC's safety ritual."""
        total_mb = stats["total_size_bytes"] / (1024 * 1024)
        
        print("\n🔥 EXORCIST MODE 🔥")
        print("━" * 60)
        print("\nHey. We need to talk about what you're about to do.")
        print(f"\nYou're about to nuke the RAG database for:")
        print(f"  📁 {self.repo}")
        print("\nHere's what that means:")
        print(f"  • {stats['span_count']:,} indexed code spans - gone")
        print(f"  • {stats['enrichment_count']:,} enriched summaries - months of LLM work, vaporized")
        print(f"  • {stats['embedding_count']:,} embeddings - all that vector magic, deleted")
        print(f"  • Every quality metric, every failure you've tracked - wiped")
        print(f"  • Total: {total_mb:.1f} MB of data")
        print("\nThis is the nuclear option. There's no undo button.")
        print("\nI get it - sometimes you need to burn it down and start fresh.")
        print("If there's a spider in there or something, I understand.")
        print("Sometimes nukes from orbit are the only way to be sure.")
        print("\nBut I care about you not shooting yourself in the foot here.")
        print("\nYou've got 5 seconds to hit Ctrl+C and walk away.")
        print("After that, it's gone for good.\n")
    
    def countdown(self) -> bool:
        """5-second countdown with Ctrl+C escape."""
        try:
            for i in range(5, 0, -1):
                print(f"Starting in {i}...")
                time.sleep(1)
            print()
        except KeyboardInterrupt:
            print("\n\n✅ Aborted. Nothing was deleted.")
            return False
        return True
    
    def confirm_repo_name(self) -> bool:
        """Require user to type repo name."""
        repo_name = self.repo.name
        print(f"Alright. Type the repo name to prove you mean it: {repo_name}")
        
        try:
            user_input = input("> ").strip()
            if user_input == repo_name:
                return True
            else:
                print(f"\n❌ Input '{user_input}' doesn't match '{repo_name}'")
                print("Aborting. Nothing was deleted.")
                return False
        except (KeyboardInterrupt, EOFError):
            print("\n\n✅ Aborted. Nothing was deleted.")
            return False
    
    def nuke(self, dry_run: bool = False) -> bool:
        """Perform the actual deletion."""
        rag_dir = self.repo / ".rag"
        
        if not rag_dir.exists():
            print(f"\n❌ No RAG database found at {rag_dir}")
            print("Nothing to exorcise.")
            return False
        
        if dry_run:
            print("\n🔍 DRY RUN - Would delete:")
            for file in self.stats.gather()["files"]:
                print(f"  {file['path']} ({file['size_bytes'] / (1024*1024):.1f} MB)")
            print("\nNo files were actually deleted (dry run mode)")
            return True
        
        print("\n✅ Confirmed. Nuking from orbit...")
        
        # Delete specific files/dirs
        if self.stats.index_db.exists():
            size_mb = self.stats.index_db.stat().st_size / (1024 * 1024)
            self.stats.index_db.unlink()
            print(f"🗑️  Deleted .rag/rag_index.db ({size_mb:.1f} MB)")
        
        if self.stats.enrichments.exists():
            self.stats.enrichments.unlink()
            print(f"🗑️  Deleted .rag/enrichments.json")
        
        if self.stats.embeddings_db.exists():
            self.stats.embeddings_db.unlink()
            print(f"🗑️  Deleted .rag/embeddings.db")
        
        if self.stats.quality_dir.exists():
            shutil.rmtree(self.stats.quality_dir)
            print(f"🗑️  Deleted .rag/quality_reports/")
        
        if self.stats.failures_db.exists():
            self.stats.failures_db.unlink()
            print(f"🗑️  Deleted .rag/failures.db")
        
        print("\n✅ Database exorcised. She's clean.")
        print("\nWant to rebuild? Run: llmc-rag force-cycle")
        
        return True
    
    def execute(self, dry_run: bool = False) -> int:
        """Full exorcist ritual."""
        # Gather stats
        stats = self.stats.gather()
        
        if not stats["exists"]:
            print(f"\n❌ No RAG database found at {self.repo / '.rag'}")
            print("Nothing to exorcise.")
            return 1
        
        if stats["span_count"] == 0 and stats["enrichment_count"] == 0:
            print(f"\nℹ️  RAG database exists but is empty.")
            print("Proceeding with cleanup...")
        
        # The Ritual
        self.print_warning(stats)
        
        if not self.countdown():
            return 1
        
        if not self.confirm_repo_name():
            return 1
        
        return 0 if self.nuke(dry_run) else 1
