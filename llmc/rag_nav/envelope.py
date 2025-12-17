# Non-disruptive envelope facade for Desktop Commander / agents
from __future__ import annotations

from typing import Any

from llmc.rag import nav_meta as core_nav_meta  # type: ignore
from llmc.rag_nav import models  # type: ignore

RagToolMeta = core_nav_meta.RagToolMeta
RagResult = core_nav_meta.RagResult
ok_result = core_nav_meta.ok_result
fallback_result = core_nav_meta.fallback_result
error_result = core_nav_meta.error_result


def _meta_from_concrete(
    source: str,
    freshness_state: str,
    *,
    status: str = "OK",
    error_code: str | None = None,
    message: str | None = None,
) -> RagToolMeta:
    """
    Construct RagToolMeta from concrete result metadata.

    This keeps adapter helpers thin and makes it easier to evolve
    freshness/source tagging without touching model types.
    """

    return RagToolMeta(
        status=status,
        error_code=error_code,
        message=message,
        source=source,
        freshness_state=freshness_state,
    )


def _has_error(res: Any) -> bool:
    """Best-effort detection of an error marker on a concrete result."""
    return bool(getattr(res, "error", None))


def _error_envelope_from(res: Any) -> RagResult[dict]:
    """
    Build an error-style RagResult from a concrete result that exposes `.error`.
    """
    err = getattr(res, "error", None)
    code = getattr(err, "code", "Error")
    message = getattr(err, "message", None)
    if message is None:
        message = str(err) if err is not None else "error"
    return error_result(error_code=code, message=str(message))


def search_to_rag_result(res: models.SearchResult) -> RagResult[models.SearchItem]:
    """
    Adapt a concrete SearchResult into a RagResult envelope.

    This preserves existing search payloads while giving Desktop Commander
    and agents a stable envelope type to depend on.
    """
    if _has_error(res):
        return _error_envelope_from(res)
    items = getattr(res, "items", [])
    source = getattr(res, "source", "RAG_GRAPH")
    freshness_state = getattr(res, "freshness_state", "UNKNOWN")
    return ok_result(items=items, source=source, freshness_state=freshness_state)


def where_used_to_rag_result(res: models.WhereUsedResult) -> RagResult[models.WhereUsedItem]:
    """
    Adapt a concrete WhereUsedResult into a RagResult envelope.
    """
    if _has_error(res):
        return _error_envelope_from(res)
    items = getattr(res, "items", [])
    source = getattr(res, "source", "RAG_GRAPH")
    freshness_state = getattr(res, "freshness_state", "UNKNOWN")
    return ok_result(items=items, source=source, freshness_state=freshness_state)


def lineage_to_rag_result(res: models.LineageResult) -> RagResult[Any]:
    """
    Adapt a concrete LineageResult into a RagResult envelope.

    Some call-sites expose lineage payloads as `edges`, others as `items`.
    The adapter tolerates both and forwards whichever is present.
    """
    if _has_error(res):
        return _error_envelope_from(res)
    payload = getattr(res, "edges", None)
    if payload is None:
        payload = getattr(res, "items", [])
    source = getattr(res, "source", "RAG_GRAPH")
    freshness_state = getattr(res, "freshness_state", "UNKNOWN")
    return ok_result(items=payload, source=source, freshness_state=freshness_state)


__all__ = [
    "RagToolMeta",
    "RagResult",
    "ok_result",
    "fallback_result",
    "error_result",
    "search_to_rag_result",
    "where_used_to_rag_result",
    "lineage_to_rag_result",
]
