"""
Direct RAG adapter for LLMC MCP server.

Calls tools.rag.search directly instead of spawning subprocess.
Provides ~5-10x speedup over CLI subprocess approach.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from llmc.config import get_llmc_config


logger = logging.getLogger(__name__)


def validate_repo_root(repo_root: str | Path) -> Path:
    """Validate repo_root is in allowed_roots.

    Raises:
        PermissionError: If repo_root is not allowed
    """
    config = get_llmc_config()
    allowed_roots = config.get("allowed_roots", [])

    # If no allowed_roots configured, allow any (backwards compat)
    if not allowed_roots:
        return Path(repo_root).resolve()

    repo_path = Path(repo_root).resolve()

    for allowed in allowed_roots:
        allowed_path = Path(allowed).resolve()
        try:
            repo_path.relative_to(allowed_path)
            return repo_path  # Valid - is under an allowed root
        except ValueError:
            continue

    raise PermissionError(f"repo_root '{repo_root}' is not under allowed_roots")


@dataclass
class RagSnippet:
    """Single RAG search result."""

    text: str
    src: str  # "path#Lstart-Lend"
    score: float
    symbol: str | None = None
    kind: str | None = None
    summary: str | None = None


@dataclass
class RagSearchResult:
    """RAG search response."""

    data: list[dict[str, Any]]
    meta: dict[str, Any]
    error: str | None = None

    @property
    def snippets(self) -> list[dict[str, Any]]:
        """Alias for data for backward compatibility."""
        return self.data

    def to_dict(self) -> dict[str, Any]:
        """Convert to standardized dictionary."""
        if self.error:
            return {"error": self.error, "meta": self.meta}
        return {"data": self.data, "meta": self.meta}


def rag_search(
    query: str,
    repo_root: Path | str,
    limit: int = 5,
    scope: str = "repo",
    debug: bool = False,
) -> RagSearchResult:
    """
    Direct RAG search - no subprocess.

    Args:
        query: Natural language query or code concept
        repo_root: Path to LLMC repo root
        limit: Max results to return
        scope: "repo", "docs", or "both" (currently ignored, uses default routing)
        debug: Include enrichment/graph metadata

    Returns:
        RagSearchResult with snippets and provenance
    """
    import os

    if not query or not query.strip():
        return RagSearchResult(data=[], meta={}, error="query is required")

    try:
        repo_path = validate_repo_root(repo_root)
    except PermissionError as e:
        return RagSearchResult(data=[], meta={}, error=str(e))

    try:
        # Direct import - module stays loaded between calls
        from llmc.rag.search import search_spans

        # The repo_path is passed to search_spans, which uses it to find
        # the llmc.toml file and load the correct configuration. This
        # replaces the need for os.chdir.
        results = search_spans(
            query.strip(),
            limit=limit,
            repo_root=repo_path,
            debug=debug,
        )

        # Transform to MCP response format (matches CLI --json output)
        snippets = [
            {
                "rank": idx + 1,
                "span_hash": r.span_hash,
                "path": str(r.path),
                "symbol": r.symbol,
                "kind": r.kind,
                "lines": [r.start_line, r.end_line],
                "score": r.score,
                "summary": r.summary,
                "debug": r.debug_info if debug else None,
            }
            for idx, r in enumerate(results)
        ]

        meta = {"count": len(snippets), "provenance": True}
        return RagSearchResult(data=snippets, meta=meta)

    except FileNotFoundError as e:
        logger.warning(f"RAG index not found: {e}")
        return RagSearchResult(
            data=[],
            meta={},
            error=f"RAG index not found. Run 'rag index' first: {e}",
        )
    except Exception as e:
        logger.exception("RAG search error")
        return RagSearchResult(data=[], meta={}, error=str(e))


def rag_search_enriched(
    query: str,
    repo_root: Path | str,
    limit: int = 5,
    enrich_mode: str = "auto",
    graph_depth: int = 1,
    include_features: bool = False,
) -> RagSearchResult:
    """
    Advanced RAG search with graph-based relationship enrichment.

    Args:
        query: Natural language query or code concept
        repo_root: Path to LLMC repo root
        limit: Max results to return
        enrich_mode: Enrichment strategy
            - "vector": Traditional semantic search only (fastest)
            - "graph": Graph-based relationship traversal only
            - "hybrid": Merge vector + graph results (most comprehensive)
            - "auto": Intelligent routing based on query analysis (recommended)
        graph_depth: Relationship traversal depth (0-3), used for graph/hybrid modes
        include_features: Include enrichment quality metrics in meta

    Returns:
        RagSearchResult with enriched snippets and optional feature metrics
    """
    import os

    if not query or not query.strip():
        return RagSearchResult(data=[], meta={}, error="query is required")

    try:
        repo_path = validate_repo_root(repo_root)
    except PermissionError as e:
        return RagSearchResult(data=[], meta={}, error=str(e))

    try:
        # For now, we'll use the existing search_spans with debug=True to get graph data
        # In future phases, we'll add proper mode selection and enrichment orchestration
        from llmc.rag.search import search_spans

        # The repo_path is passed to search_spans, which uses it to find
        # the llmc.toml file and load the correct configuration. This
        # replaces the need for os.chdir.
        # Enable debug mode to get graph enrichment
        use_debug = (enrich_mode in ["graph", "hybrid", "auto"]) or include_features

        results = search_spans(
            query.strip(),
            limit=limit,
            repo_root=repo_path,
            debug=use_debug,
        )

        # Transform to MCP response format
        snippets = [
            {
                "rank": idx + 1,
                "span_hash": r.span_hash,
                "path": str(r.path),
                "symbol": r.symbol,
                "kind": r.kind,
                "lines": [r.start_line, r.end_line],
                "score": r.score,
                "summary": r.summary,
                "debug": r.debug_info if use_debug else None,
            }
            for idx, r in enumerate(results)
        ]

        # Build metadata
        meta = {
            "count": len(snippets),
            "provenance": True,
            "enrich_mode": enrich_mode,
        }

        # Add enrichment features if requested
        if include_features:
            # Analyze query to extract features
            # For now, provide basic metrics based on debug data
            has_graph = any(s.get("debug", {}).get("graph") for s in snippets if s.get("debug"))
            has_enrichment = any(
                s.get("debug", {}).get("enrichment") for s in snippets if s.get("debug")
            )

            meta["enrichment_features"] = {
                "graph_available": has_graph,
                "enrichment_available": has_enrichment,
                "graph_depth_used": graph_depth,
                "mode_used": enrich_mode,
            }

        return RagSearchResult(data=snippets, meta=meta)

    except FileNotFoundError as e:
        logger.warning(f"RAG index not found: {e}")
        return RagSearchResult(
            data=[],
            meta={},
            error=f"RAG index not found. Run 'rag index' first: {e}",
        )
    except Exception as e:
        logger.exception("RAG search enriched error")
        return RagSearchResult(data=[], meta={}, error=str(e))


def rag_bootload(
    session_id: str,
    task_id: str,
    repo_root: Path | str,
) -> dict[str, Any]:
    """
    RAG bootloader - returns minimal context for session initialization.

    Per SDD: Returns plan/scope/notes based on AGENTS/CONTRACTS.

    Args:
        session_id: Session identifier
        task_id: Task identifier
        repo_root: Path to LLMC repo root

    Returns:
        Dict with plan, scope, notes
    """
    try:
        repo_path = validate_repo_root(repo_root)
    except PermissionError as e:
        return {"error": str(e)}

    # For MVP, return minimal bootstrap info
    # Future: Parse task_id to determine scope, load relevant context
    return {
        "session_id": session_id,
        "task_id": task_id,
        "plan": "Use rag_search for code context, read_file for specific files",
        "scope": "repo",
        "notes": f"LLMC repo at {repo_path}",
        "tools_available": ["rag_search", "read_file", "list_dir", "stat"],
    }
