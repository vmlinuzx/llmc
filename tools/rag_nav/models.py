"""Core data models for RAG Nav.

This module defines:
 - IndexStatus alias used by metadata helpers.
 - SnippetLocation / Snippet containers for code fragments.
 - Result item / envelope types for search, where-used, and lineage tools.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Literal, Optional

from tools.rag.freshness import (
    FreshnessState as _FreshnessState,
    IndexState as _IndexState,
    IndexStatus as _IndexStatus,
)

# ---------------------------------------------------------------------------
# Index metadata aliases
# ---------------------------------------------------------------------------

# Re-export core index freshness types so callers can depend on a single
# canonical definition without duplicating schemas.
IndexState = _IndexState
FreshnessState = _FreshnessState
IndexStatus = _IndexStatus

# Source tag used for RAG-only tools. Task 4 will set this to either
# "RAG_GRAPH" or "LOCAL_FALLBACK" depending on routing decisions.
SourceTag = Literal["RAG_GRAPH", "LOCAL_FALLBACK"]


# ---------------------------------------------------------------------------
# Snippet containers
# ---------------------------------------------------------------------------

@dataclass
class SnippetLocation:
    """Location of a snippet within a source file."""

    path: str
    start_line: int
    end_line: int


@dataclass
class Snippet:
    """A small window of source text with location metadata."""

    text: str
    location: SnippetLocation


# ---------------------------------------------------------------------------
# Search / Where-Used / Lineage result models
# ---------------------------------------------------------------------------

@dataclass
class EnrichmentData:
    """Semantic enrichment for a code entity."""
    summary: Optional[str] = None
    usage_guide: Optional[str] = None
    content_type: Optional[str] = None
    content_language: Optional[str] = None
    # Extensible for future fields (inputs, outputs, etc.)
    
    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class SearchItem:
    """Single search hit within a repository."""

    file: str
    snippet: Snippet
    enrichment: Optional[EnrichmentData] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.enrichment:
            d["enrichment"] = self.enrichment.to_dict()
        return d


@dataclass
class SearchResult:
    """Result envelope for code search queries."""

    query: str
    items: List[SearchItem]
    truncated: bool = False
    source: SourceTag = "RAG_GRAPH"
    freshness_state: FreshnessState = "UNKNOWN"
    
    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "items": [item.to_dict() for item in self.items],
            "truncated": self.truncated,
            "source": self.source,
            "freshness_state": self.freshness_state,
        }


@dataclass
class WhereUsedItem:
    """Single where-used hit indicating a usage location for a symbol."""

    file: str
    snippet: Snippet
    enrichment: Optional[EnrichmentData] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.enrichment:
            d["enrichment"] = self.enrichment.to_dict()
        return d


@dataclass
class WhereUsedResult:
    """Result envelope for where-used queries."""

    symbol: str
    items: List[WhereUsedItem]
    truncated: bool = False
    source: SourceTag = "RAG_GRAPH"
    freshness_state: FreshnessState = "UNKNOWN"

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "items": [item.to_dict() for item in self.items],
            "truncated": self.truncated,
            "source": self.source,
            "freshness_state": self.freshness_state,
        }


@dataclass
class LineageItem:
    """Single lineage hop for a symbol."""

    file: str
    snippet: Snippet
    enrichment: Optional[EnrichmentData] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.enrichment:
            d["enrichment"] = self.enrichment.to_dict()
        return d


@dataclass
class LineageResult:
    """Result envelope for lineage queries."""

    symbol: str
    direction: str
    items: List[LineageItem]
    truncated: bool = False
    source: SourceTag = "RAG_GRAPH"
    freshness_state: FreshnessState = "UNKNOWN"

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "items": [item.to_dict() for item in self.items],
            "truncated": self.truncated,
            "source": self.source,
            "freshness_state": self.freshness_state,
        }


__all__ = [
    "IndexState",
    "FreshnessState",
    "IndexStatus",
    "SourceTag",
    "SnippetLocation",
    "Snippet",
    "EnrichmentData",
    "SearchItem",
    "SearchResult",
    "WhereUsedItem",
    "WhereUsedResult",
    "LineageItem",
    "LineageResult",
]
