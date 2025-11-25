#!/usr/bin/env python3
"""
query_context.py - Query RAG system for relevant code context

Usage:
    python query_context.py "authentication system"
    python query_context.py "supabase queries" --project glideclubs
    python query_context.py "api routes" --limit 5
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

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
        if local_path.exists():
            return local_path
    elif env_path == "global":
        global_path = Path.home() / ".deepseek_rag"
        if global_path.exists():
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


CHROMA_DB_PATH = resolve_rag_db_path()
COLLECTION_NAME = "workspace_code"


class ContextQuerier:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.query_prefix = os.getenv("LLMC_RAG_QUERY_PREFIX", "query: ")

        # Initialize ChromaDB
        try:
            self.client = chromadb.PersistentClient(
                path=str(db_path),
                settings=Settings(anonymized_telemetry=False)
            )
            self.collection = self.client.get_collection(COLLECTION_NAME)
        except Exception as e:
            print(f"❌ Error: RAG database not found at {db_path}")
            print(f"   Run 'python index_workspace.py' first to create the index")
            sys.exit(1)

        # Initialize embedding model
        model_name = os.getenv("LLMC_RAG_WORKSPACE_MODEL", "intfloat/e5-base-v2")
        self.model = SentenceTransformer(model_name)
    
    def query(
        self,
        query_text: str,
        project: Optional[str] = None,
        file_type: Optional[str] = None,
        limit: int = 10,
        include_related: bool = True
    ) -> List[Dict]:
        """Query for relevant code context"""
        
        # Build where filter
        where = {}
        if project:
            where["project"] = project
        if file_type:
            where["file_ext"] = file_type
        
        # Generate query embedding
        prefixed_query = f"{self.query_prefix}{query_text.strip()}"
        query_embedding = self.model.encode([prefixed_query], normalize_embeddings=True)[0]
        
        # Query collection
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=limit,
            where=where if where else None
        )
        
        # Format results
        contexts = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                context = {
                    "text": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "distance": results['distances'][0][i],
                    "relevance": 1.0 - results['distances'][0][i]  # Convert distance to relevance
                }
                contexts.append(context)
        
        return contexts
    
    def build_context_for_task(
        self,
        task: str,
        project: str,
        max_tokens: int = 8000
    ) -> str:
        """Build comprehensive context for a coding task"""
        
        # Query for relevant chunks
        contexts = self.query(task, project=project, limit=20)
        
        if not contexts:
            return f"Project: {project}\nNo relevant context found.\n"
        
        # Build context string within token budget
        context_parts = [
            f"# Project: {project}",
            f"# Task: {task}",
            "",
            "## Relevant Code Context:",
            ""
        ]
        
        current_tokens = sum(len(part.split()) for part in context_parts)
        files_included = set()
        
        for ctx in contexts:
            file_path = ctx['metadata'].get('file_path', 'unknown')
            relevance = ctx['relevance']
            
            # Format chunk with metadata
            chunk_text = f"\n### {file_path} (relevance: {relevance:.2f})\n```\n{ctx['text']}\n```\n"
            chunk_tokens = len(chunk_text.split())
            
            # Check token budget
            if current_tokens + chunk_tokens > max_tokens:
                break
            
            context_parts.append(chunk_text)
            current_tokens += chunk_tokens
            files_included.add(file_path)
        
        # Add summary
        context_parts.insert(4, f"## Files referenced: {len(files_included)}")
        context_parts.insert(5, "")
        
        return "\n".join(context_parts)


def main():
    parser = argparse.ArgumentParser(description="Query RAG system for code context")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--project", help="Filter by project name")
    parser.add_argument("--type", help="Filter by file type (e.g., .py, .ts)")
    parser.add_argument("--limit", type=int, default=10, help="Number of results")
    parser.add_argument("--context", action="store_true", help="Build full context for task")
    parser.add_argument("--max-tokens", type=int, default=8000, help="Max tokens for context")
    
    args = parser.parse_args()
    
    querier = ContextQuerier(CHROMA_DB_PATH)
    
    if args.context:
        # Build full context
        if not args.project:
            print("❌ --project required when using --context")
            sys.exit(1)
        
        context = querier.build_context_for_task(
            args.query,
            args.project,
            max_tokens=args.max_tokens
        )
        print(context)
    else:
        # Simple query
        results = querier.query(
            args.query,
            project=args.project,
            file_type=args.type,
            limit=args.limit
        )
        
        if not results:
            print("No results found")
            return
        
        print(f"\n🔍 Found {len(results)} results for: '{args.query}'\n")
        
        for i, result in enumerate(results, 1):
            meta = result['metadata']
            relevance = result['relevance']
            
            print(f"{'='*80}")
            print(f"Result {i} - Relevance: {relevance:.3f}")
            print(f"File: {meta.get('file_path', 'unknown')}")
            print(f"Project: {meta.get('project', 'unknown')}")
            if 'last_commit' in meta:
                print(f"Last commit: {meta['last_commit']} by {meta.get('last_author', 'unknown')}")
            print(f"\n{result['text'][:500]}...")
            print()


if __name__ == "__main__":
    main()
