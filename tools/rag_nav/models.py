from __future__ import annotations

"""Core data models for RAG Nav.

This module defines:
 - IndexStatus alias used by metadata helpers.
 - SnippetLocation / Snippet containers for code fragments.
 - Result item / envelope types for search, where-used, and lineage tools.
"""

from dataclasses import dataclass
from typing import List, Literal

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
class SearchItem:
    """Single search hit within a repository."""

    file: str
    snippet: Snippet


@dataclass
class SearchResult:
    """Result envelope for code search queries."""

    query: str
    items: List[SearchItem]
    truncated: bool = False
    source: SourceTag = "RAG_GRAPH"
    freshness_state: FreshnessState = "UNKNOWN"


@dataclass
class WhereUsedItem:
    """Single where-used hit indicating a usage location for a symbol."""

    file: str
    snippet: Snippet


@dataclass
class WhereUsedResult:
    """Result envelope for where-used queries."""

    symbol: str
    items: List[WhereUsedItem]
    truncated: bool = False
    source: SourceTag = "RAG_GRAPH"
    freshness_state: FreshnessState = "UNKNOWN"


@dataclass
class LineageItem:
    """Single lineage hop for a symbol."""

    file: str
    snippet: Snippet


@dataclass
class LineageResult:
    """Result envelope for lineage queries."""

    symbol: str
    direction: str
    items: List[LineageItem]
    truncated: bool = False
    source: SourceTag = "RAG_GRAPH"
    freshness_state: FreshnessState = "UNKNOWN"


__all__ = [
    "IndexState",
    "FreshnessState",
    "IndexStatus",
    "SourceTag",
    "SnippetLocation",
    "Snippet",
    "SearchItem",
    "SearchResult",
    "WhereUsedItem",
    "WhereUsedResult",
    "LineageItem",
    "LineageResult",
]
