from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Generic, Literal, Optional, TypeVar
from collections.abc import Sequence

from .freshness import FreshnessState, IndexStatus

RagToolStatus = Literal["OK", "FALLBACK", "ERROR"]
RagToolSource = Literal["RAG_GRAPH", "LOCAL_FALLBACK", "NONE"]


@dataclass
class RagToolMeta:
    """
    Metadata attached to all RAG navigation-style tool responses.

    This is what MCP clients and Desktop Commander should inspect to decide
    whether the result is authoritative, a deterministic fallback, or an error.
    """

    status: RagToolStatus = "OK"
    error_code: Optional[str] = None
    message: Optional[str] = None

    source: RagToolSource = "RAG_GRAPH"
    freshness_state: FreshnessState = "UNKNOWN"

    # Optional snapshot of the index status used for this decision.
    index_status: Optional[IndexStatus] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.index_status is not None and hasattr(self.index_status, "to_dict"):
            data["index_status"] = self.index_status.to_dict()
        return data


T = TypeVar("T")


@dataclass
class RagResult(Generic[T]):
    """
    Generic envelope for RAG-style tool results.
    """

    meta: RagToolMeta
    items: Sequence[T] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        def _item_to_dict(item):
            if hasattr(item, "to_dict"):
                return item.to_dict()
            if hasattr(item, "_asdict"):
                return item._asdict()
            return item

        return {
            "meta": self.meta.to_dict(),
            "items": [_item_to_dict(item) for item in self.items],
        }


def ok_result(
    items: Sequence[T],
    *,
    source: RagToolSource = "RAG_GRAPH",
    freshness_state: FreshnessState = "FRESH",
    index_status: Optional[IndexStatus] = None,
    message: Optional[str] = None,
) -> RagResult[T]:
    return RagResult(
        meta=RagToolMeta(
            status="OK",
            error_code=None,
            message=message,
            source=source,
            freshness_state=freshness_state,
            index_status=index_status,
        ),
        items=items,
    )


def fallback_result(
    items: Sequence[T],
    *,
    freshness_state: FreshnessState = "STALE",
    index_status: Optional[IndexStatus] = None,
    message: Optional[str] = None,
) -> RagResult[T]:
    return RagResult(
        meta=RagToolMeta(
            status="FALLBACK",
            error_code=None,
            message=message,
            source="LOCAL_FALLBACK",
            freshness_state=freshness_state,
            index_status=index_status,
        ),
        items=items,
    )


def error_result(
    *,
    error_code: str,
    message: str,
    freshness_state: FreshnessState = "UNKNOWN",
    index_status: Optional[IndexStatus] = None,
) -> RagResult[dict]:
    """
    Represent an error as a RagResult with no items and a structured error meta.
    """
    return RagResult(
        meta=RagToolMeta(
            status="ERROR",
            error_code=error_code,
            message=message,
            source="NONE",
            freshness_state=freshness_state,
            index_status=index_status,
        ),
        items=(),
    )
