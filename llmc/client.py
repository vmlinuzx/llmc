#!/usr/bin/env python3
"""LLMC RAG Client - Unified facade for RAG operations."""
from pathlib import Path
from typing import Optional, Dict, Any
from tools.rag_nav.tool_handlers import (
    tool_rag_search,
    tool_rag_where_used,
    tool_rag_lineage,
    tool_rag_stats,
    build_graph_for_repo
)
from tools.rag_nav.models import SearchResult, WhereUsedResult, LineageResult
from tools.rag_nav.metadata import load_status

class RAGClient:
    """
    Unified Client Facade for the LLMC RAG System.
    
    This class abstracts the underlying tool handlers and provides a clean
    API for the TUI and other consumers to interact with the RAG service.
    """
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    def search(self, query: str, limit: Optional[int] = None) -> SearchResult:
        """Search the codebase using RAG (FTS + Graph) or local fallback."""
        return tool_rag_search(self.repo_root, query, limit)

    def where_used(self, symbol: str, limit: Optional[int] = None) -> WhereUsedResult:
        """Find usages of a symbol."""
        return tool_rag_where_used(self.repo_root, symbol, limit)

    def lineage(self, symbol: str, direction: str = "downstream", limit: Optional[int] = None) -> LineageResult:
        """Trace data flow (upstream/downstream)."""
        return tool_rag_lineage(self.repo_root, symbol, direction, limit)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system health and graph statistics."""
        stats = tool_rag_stats(self.repo_root)
        status = load_status(self.repo_root)
        if status:
            stats["freshness"] = status.index_state
            stats["last_indexed"] = status.last_indexed_at
        else:
            stats["freshness"] = "UNKNOWN"
            stats["last_indexed"] = None
        return stats

    def rebuild_graph(self) -> Any:
        """Triggers a graph rebuild (synchronous)."""
        return build_graph_for_repo(self.repo_root)
