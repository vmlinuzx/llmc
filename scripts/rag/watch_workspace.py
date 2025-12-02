#!/usr/bin/env python3
"""
watch_workspace.py - Auto-reindex files when they change

Usage:
    python watch_workspace.py                    # Watch entire workspace
    python watch_workspace.py --project glideclubs  # Watch one project
"""

import argparse
from datetime import datetime
from pathlib import Path
import time

from index_workspace import (
    CHROMA_DB_PATH,
    CODE_EXTENSIONS,
    EXCLUDE_DIRS,
    WORKSPACE_ROOT,
    WorkspaceIndexer,
)
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class CodeFileHandler(FileSystemEventHandler):
    def __init__(self, indexer: WorkspaceIndexer, project_filter: Optional[str] = None):
        self.indexer = indexer
        self.project_filter = project_filter
        self.last_indexed = {}  # Debounce rapid changes
        self.debounce_seconds = 2
    
    def should_process(self, file_path: Path) -> bool:
        """Check if file should be processed"""
        # Check extension
        if file_path.suffix not in CODE_EXTENSIONS:
            return False
        
        # Check excluded dirs
        for parent in file_path.parents:
            if parent.name in EXCLUDE_DIRS:
                return False
        
        # Check project filter
        if self.project_filter:
            try:
                rel = file_path.relative_to(WORKSPACE_ROOT)
                if not str(rel).startswith(self.project_filter):
                    return False
            except:
                return False
        
        # Debounce
        now = time.time()
        last = self.last_indexed.get(str(file_path), 0)
        if now - last < self.debounce_seconds:
            return False
        
        return True
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if not self.should_process(file_path):
            return
        
        print(f"📝 {datetime.now().strftime('%H:%M:%S')} - File modified: {file_path.name}")
        
        try:
            chunks = self.indexer.index_file(file_path)
            if chunks > 0:
                print(f"   ✅ Indexed {chunks} chunks")
            self.last_indexed[str(file_path)] = time.time()
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if not self.should_process(file_path):
            return
        
        print(f"➕ {datetime.now().strftime('%H:%M:%S')} - File created: {file_path.name}")
        
        try:
            chunks = self.indexer.index_file(file_path)
            if chunks > 0:
                print(f"   ✅ Indexed {chunks} chunks")
            self.last_indexed[str(file_path)] = time.time()
        except Exception as e:
            print(f"   ❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Watch workspace and auto-reindex changes")
    parser.add_argument("--project", help="Watch specific project only")
    
    args = parser.parse_args()
    
    print("🔍 Initializing workspace watcher...")
    indexer = WorkspaceIndexer(WORKSPACE_ROOT, CHROMA_DB_PATH)
    
    watch_path = WORKSPACE_ROOT
    if args.project:
        watch_path = WORKSPACE_ROOT / args.project
        if not watch_path.exists():
            print(f"❌ Project not found: {watch_path}")
            return
    
    print(f"👀 Watching: {watch_path}")
    print(f"💾 DB: {CHROMA_DB_PATH}")
    print("⏸️  Press Ctrl+C to stop\n")
    
    event_handler = CodeFileHandler(indexer, args.project)
    observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping watcher...")
        observer.stop()
    
    observer.join()
    print("✅ Watcher stopped")


if __name__ == "__main__":
    main()
