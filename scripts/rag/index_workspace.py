#!/usr/bin/env python3
"""
index_workspace.py - Index entire ~/src/ workspace for DeepSeek RAG

Usage:
    python index_workspace.py                    # Index everything
    python index_workspace.py --project glideclubs  # Index one project
    python index_workspace.py --reindex          # Force reindex all
"""

import os
import sys
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import argparse

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import git

from ast_chunker import ASTChunker

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.rag.config import get_exclude_dirs

# Configuration
def resolve_rag_db_path() -> Path:
    """
    Resolve RAG database path with fallback logic.
    Priority: global → local → environment variable
    """
    # Check environment variable first
    env_path = os.getenv("LLMC_RAG_MODE")
    if env_path == "local":
        local_path = Path.cwd() / ".rag" / "chroma_db"
        return local_path
    elif env_path == "global":
        global_path = Path.home() / ".deepseek_rag"
        return global_path
    
    # Auto mode: try global first (cross-project), then local (repo-specific)
    global_path = Path.home() / ".deepseek_rag"
    if global_path.exists():
        return global_path
    
    local_path = Path.cwd() / ".rag" / "chroma_db"
    if local_path.exists():
        return local_path
    
    # Default to global path for creation
    return global_path


WORKSPACE_ROOT = Path.home() / "src"
CHROMA_DB_PATH = resolve_rag_db_path()
COLLECTION_NAME = "workspace_code"

# Exclusions


EXCLUDE_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dll", ".dylib",
    ".exe", ".bin", ".dat", ".log",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".bz2",
    ".mp3", ".mp4", ".avi", ".mov",
    ".lock"  # package-lock.json, etc.
}

# File types we want to index
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".sql", ".sh", ".bash", ".zsh",
    ".md", ".mdx", ".txt",
    ".json", ".yaml", ".yml", ".toml",
    ".css", ".scss", ".sass",
    ".html", ".xml",
    ".go", ".rs", ".c", ".cpp", ".h",
    ".java", ".kt", ".swift",
    ".rb", ".php", ".lua"
}

# Chunk settings
CHUNK_SIZE = 1000  # characters
CHUNK_OVERLAP = 200  # characters


class WorkspaceIndexer:
    def __init__(self, workspace_root: Path, db_path: Path):
        self.workspace_root = workspace_root
        self.db_path = db_path
        self.passage_prefix = os.getenv("LLMC_RAG_PASSAGE_PREFIX", "passage: ")
        self.chunker = ASTChunker(max_chars=CHUNK_SIZE, overlap_chars=CHUNK_OVERLAP)

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(COLLECTION_NAME)
            print(f"✅ Loaded existing collection: {COLLECTION_NAME}")
        except:
            self.collection = self.client.create_collection(
                name=COLLECTION_NAME,
                metadata={"description": "Workspace code embeddings"}
            )
            print(f"✅ Created new collection: {COLLECTION_NAME}")
        
        # Initialize embedding model (runs locally!)
        print("🔄 Loading embedding model (sentence-transformers)...")
        model_name = os.getenv("LLMC_RAG_WORKSPACE_MODEL", "intfloat/e5-base-v2")
        self.model = SentenceTransformer(model_name)
        print("✅ Embedding model loaded")
    
    def should_index_file(self, file_path: Path) -> bool:
        """Check if file should be indexed"""
        # Check extension
        if file_path.suffix.lower() not in CODE_EXTENSIONS:
            return False
        
        # Check if in excluded directory
        for parent in file_path.parents:
            if parent.name in get_exclude_dirs(REPO_ROOT):
                return False
        
        # Check file size (skip huge files)
        try:
            if file_path.stat().st_size > 1_000_000:  # 1MB
                return False
        except:
            return False
        
        return True
    
    def get_project_name(self, file_path: Path) -> str:
        """Extract project name from file path"""
        try:
            relative = file_path.relative_to(self.workspace_root)
            return str(relative.parts[0]) if relative.parts else "unknown"
        except:
            return "unknown"
    
    def get_git_info(self, file_path: Path) -> Optional[Dict]:
        """Get git info for file if available"""
        try:
            repo = git.Repo(file_path, search_parent_directories=True)
            last_commit = next(repo.iter_commits(paths=str(file_path), max_count=1))
            return {
                "last_commit": last_commit.hexsha[:8],
                "last_author": last_commit.author.name,
                "last_modified": datetime.fromtimestamp(last_commit.committed_date).isoformat()
            }
        except:
            return None
    
    def chunk_text(self, text: str, file_path: str) -> List[Tuple[str, Dict]]:
        """Delegate to AST-aware chunker with fallback."""
        try:
            chunks = self.chunker.chunk_text(text, file_path)
            if chunks:
                return chunks
        except Exception as exc:
            print(f"⚠️  AST chunker failed for {file_path}: {exc}")
        # Fallback to legacy windowing if AST strategy unavailable
        return self.chunker.fallback_chunks(text)
    
    def file_hash(self, file_path: Path) -> str:
        """Generate hash of file content"""
        hasher = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                hasher.update(f.read())
            return hasher.hexdigest()
        except:
            return ""
    
    def index_file(self, file_path: Path) -> int:
        """Index a single file, return number of chunks added"""
        try:
            # Read file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if not content.strip():
                return 0
            
            # Generate file hash for deduplication
            file_hash = self.file_hash(file_path)
            
            # Check if already indexed with same hash
            existing = self.collection.get(
                where={"file_hash": file_hash},
                limit=1
            )
            if existing['ids']:
                return 0  # Already indexed, skip
            
            # Get metadata
            project = self.get_project_name(file_path)
            git_info = self.get_git_info(file_path)
            
            # Chunk the content
            chunks = self.chunk_text(content, str(file_path))
            
            # Prepare for insertion
            ids = []
            texts = []
            metadatas = []
            
            for i, (chunk_text, chunk_meta) in enumerate(chunks):
                doc_id = f"{file_hash}_{i}"
                ids.append(doc_id)
                texts.append(chunk_text)
                
                metadata = {
                    "project": project,
                    "file_path": str(file_path.relative_to(self.workspace_root)),
                    "file_name": file_path.name,
                    "file_ext": file_path.suffix,
                    "file_hash": file_hash,
                    "indexed_at": datetime.now().isoformat()
                }
                
                if git_info:
                    metadata.update(git_info)
                
                if isinstance(chunk_meta, dict):
                    metadata.update(chunk_meta)
                metadata["chunk_id"] = i
                
                metadatas.append(metadata)
            
            # Generate embeddings and add to collection
            if texts:
                prefixed = [f"{self.passage_prefix}{text}" for text in texts]
                embeddings = self.model.encode(
                    prefixed,
                    show_progress_bar=False,
                    normalize_embeddings=True,
                )
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings.tolist(),
                    documents=texts,
                    metadatas=metadatas
                )
            
            return len(chunks)
            
        except Exception as e:
            print(f"❌ Error indexing {file_path}: {e}")
            return 0
    
    def index_workspace(self, project_filter: Optional[str] = None, reindex: bool = False):
        """Index entire workspace or specific project"""
        print(f"\n🔍 Scanning workspace: {self.workspace_root}")
        
        # Find all files to index
        files_to_index = []
        for root, dirs, files in os.walk(self.workspace_root):
            # Filter directories
            dirs[:] = [d for d in dirs if d not in get_exclude_dirs(REPO_ROOT)]
            
            root_path = Path(root)
            
            # Project filter
            if project_filter:
                try:
                    rel = root_path.relative_to(self.workspace_root)
                    if not str(rel).startswith(project_filter):
                        continue
                except:
                    continue
            
            for file in files:
                file_path = root_path / file
                if self.should_index_file(file_path):
                    files_to_index.append(file_path)
        
        print(f"📁 Found {len(files_to_index)} files to index")
        
        if not files_to_index:
            print("⚠️  No files found to index")
            return
        
        # Clear if reindexing
        if reindex:
            print("🗑️  Clearing existing index...")
            self.client.delete_collection(COLLECTION_NAME)
            self.collection = self.client.create_collection(
                name=COLLECTION_NAME,
                metadata={"description": "Workspace code embeddings"}
            )
        
        # Index files with progress bar
        total_chunks = 0
        indexed_files = 0
        
        with tqdm(total=len(files_to_index), desc="Indexing") as pbar:
            for file_path in files_to_index:
                chunks = self.index_file(file_path)
                if chunks > 0:
                    total_chunks += chunks
                    indexed_files += 1
                pbar.update(1)
                pbar.set_postfix({
                    "files": indexed_files,
                    "chunks": total_chunks
                })
        
        print(f"\n✅ Indexing complete!")
        print(f"   Files indexed: {indexed_files}")
        print(f"   Total chunks: {total_chunks}")
        print(f"   DB location: {self.db_path}")
    
    def get_stats(self) -> Dict:
        """Get collection statistics"""
        count = self.collection.count()
        
        # Get unique projects
        results = self.collection.get(limit=count)
        projects = set()
        file_types = {}
        
        for meta in results['metadatas']:
            projects.add(meta.get('project', 'unknown'))
            ext = meta.get('file_ext', 'unknown')
            file_types[ext] = file_types.get(ext, 0) + 1
        
        return {
            "total_chunks": count,
            "projects": len(projects),
            "project_list": sorted(projects),
            "file_types": file_types
        }


def main():
    parser = argparse.ArgumentParser(description="Index workspace for DeepSeek RAG")
    parser.add_argument("--project", help="Index specific project only")
    parser.add_argument("--reindex", action="store_true", help="Force reindex all files")
    parser.add_argument("--stats", action="store_true", help="Show collection statistics")
    
    args = parser.parse_args()
    
    indexer = WorkspaceIndexer(WORKSPACE_ROOT, CHROMA_DB_PATH)
    
    if args.stats:
        stats = indexer.get_stats()
        print(f"\n📊 Collection Statistics")
        print(f"   Total chunks: {stats['total_chunks']}")
        print(f"   Projects indexed: {stats['projects']}")
        print(f"   Project list: {', '.join(stats['project_list'])}")
        print(f"\n   File types:")
        for ext, count in sorted(stats['file_types'].items(), key=lambda x: -x[1])[:10]:
            print(f"     {ext}: {count}")
    else:
        indexer.index_workspace(
            project_filter=args.project,
            reindex=args.reindex
        )


if __name__ == "__main__":
    main()
