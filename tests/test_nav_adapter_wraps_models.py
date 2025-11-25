# Validates adapter helpers wrap existing concrete result models into RagResult
from tools.rag_nav import models
from tools.rag_nav.envelope import (
    lineage_to_rag_result,
    search_to_rag_result,
    where_used_to_rag_result,
)


def test_search_adapter_ok():
    # Build a minimal concrete SearchResult-like object
    if hasattr(models, "SearchResult"):
        res = models.SearchResult(
            query="q",
            items=[],
            source="RAG_GRAPH",
            freshness_state="FRESH",
        )
    else:
        res = type(
            "X",
            (object,),
            {"items": [1], "source": "RAG_GRAPH", "freshness_state": "FRESH"},
        )()
    r = search_to_rag_result(res)
    assert r.meta.status == "OK"
    assert hasattr(r, "items")


def test_where_used_adapter_ok():
    if hasattr(models, "WhereUsedResult"):
        res = models.WhereUsedResult(
            symbol="x",
            items=[],
            source="RAG_GRAPH",
            freshness_state="UNKNOWN",
        )
    else:
        res = type(
            "X",
            (object,),
            {"items": [], "source": "RAG_GRAPH", "freshness_state": "UNKNOWN"},
        )()
    r = where_used_to_rag_result(res)
    assert r.meta.source in {"RAG_GRAPH", "LOCAL_FALLBACK", "NONE"}


def test_lineage_adapter_ok():
    # Some repos call payload 'edges' for lineage; honor that
    if hasattr(models, "LineageResult"):
        res = models.LineageResult(
            symbol="x",
            direction="downstream",
            items=[],
            source="RAG_GRAPH",
            freshness_state="UNKNOWN",
        )
    else:
        res = type(
            "X",
            (object,),
            {"edges": [], "source": "RAG_GRAPH", "freshness_state": "UNKNOWN"},
        )()
    r = lineage_to_rag_result(res)
    assert hasattr(r, "items") or hasattr(r, "meta")
    assert r.meta.freshness_state in {"FRESH", "STALE", "UNKNOWN"}

