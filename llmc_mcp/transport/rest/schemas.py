"""Response models for REST API endpoints."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ErrorDetail:
    """Structured error response."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {"code": self.code, "message": self.message}
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class ErrorResponse:
    """Top-level error envelope."""

    error: ErrorDetail

    def to_dict(self) -> dict:
        return {"error": self.error.to_dict()}


@dataclass
class PaginationInfo:
    """Pagination metadata for list responses."""

    cursor: str | None = None
    has_more: bool = False
    total_estimate: int | None = None
    total: int | None = None

    def to_dict(self) -> dict:
        d = {"has_more": self.has_more}
        if self.cursor:
            d["cursor"] = self.cursor
        if self.total_estimate is not None:
            d["total_estimate"] = self.total_estimate
        if self.total is not None:
            d["total"] = self.total
        return d


@dataclass
class SearchMeta:
    """Metadata for search responses."""

    search_time_ms: int
    route: str = "code"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkspaceInfo:
    """Workspace metadata."""

    id: str
    path: str
    indexed: bool
    span_count: int | None = None
    last_indexed: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "path": self.path,
            "indexed": self.indexed,
            "span_count": self.span_count,
            "last_indexed": self.last_indexed,
        }


@dataclass
class HealthResponse:
    """Health check response."""

    status: str = "ok"
    version: str = "1.0.0"
    api: str = "rest"
    workspaces: list[str] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SpanResult:
    """Single search result span."""

    path: str
    kind: str
    name: str
    start_line: int
    end_line: int
    content: str
    docstring: str | None = None
    score: float = 0.0
    file_description: str | None = None
    language: str | None = None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "span": {
                "kind": self.kind,
                "name": self.name,
                "start_line": self.start_line,
                "end_line": self.end_line,
                "content": self.content,
                "docstring": self.docstring,
            },
            "score": self.score,
            "file_description": self.file_description,
            "language": self.language,
        }


@dataclass
class ReferenceResult:
    """Single reference/usage result."""

    path: str
    line: int
    context: str
    kind: str = "reference"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LineageNode:
    """Single node in lineage graph."""

    symbol: str
    path: str
    line: int
    depth: int = 1

    def to_dict(self) -> dict:
        return asdict(self)
