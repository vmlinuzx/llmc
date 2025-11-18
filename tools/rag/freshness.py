from __future__ import annotations

"""
Core freshness types for LLMC RAG.

This module provides a minimal, stable definition of the index status
and freshness state used across RAG components. It intentionally mirrors
the SDD for RAG Nav metadata without depending on any specific nav
implementation module layout.
"""

from dataclasses import dataclass
from typing import Literal, Optional

IndexState = Literal["fresh", "stale", "rebuilding", "error"]
FreshnessState = Literal["FRESH", "STALE", "UNKNOWN"]


@dataclass
class IndexStatus:
    """Status metadata for a repository's RAG index/graph."""

    repo: str
    index_state: IndexState
    last_indexed_at: str  # ISO 8601 timestamp in UTC
    last_indexed_commit: Optional[str]
    schema_version: str
    last_error: Optional[str] = None

    def to_dict(self) -> dict:
        data = {
            "repo": self.repo,
            "index_state": self.index_state,
            "last_indexed_at": self.last_indexed_at,
            "last_indexed_commit": self.last_indexed_commit,
            "schema_version": self.schema_version,
        }
        if self.last_error is not None:
            data["last_error"] = self.last_error
        return data


__all__ = ["IndexState", "FreshnessState", "IndexStatus"]

