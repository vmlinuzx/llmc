"""Validate we can create OK and ERROR envelopes via nav_meta."""

from tools.rag import nav_meta as core_nav_meta
from tools.rag_nav.envelope import RagToolMeta, error_result, ok_result


def test_ok_error_factories():
    # Ensure we can still import the core module for compatibility.
    assert hasattr(core_nav_meta, "RagToolMeta")

    meta = RagToolMeta(status="OK", source="RAG_GRAPH", freshness_state="FRESH")
    ok_res = ok_result(items=[1, 2, 3], source=meta.source, freshness_state=meta.freshness_state)
    assert ok_res.meta.status == "OK"
    assert len(ok_res.items) == 3

    err_res = error_result(error_code="Boom", message="kaboom")
    assert err_res.meta.status == "ERROR"
    assert err_res.meta.error_code == "Boom"
