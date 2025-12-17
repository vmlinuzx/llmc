from types import SimpleNamespace

from llmc.rag.schema import Entity
from llmc.rag_nav.tool_handlers import _attach_enrichment_to_entity


def make_entity():
    return Entity(
        id="func:demo",
        kind="function",
        path="src/demo.py:1-3",
        metadata={},
        span_hash=None,
        file_path="src/demo.py",
        start_line=1,
        end_line=3,
    )


def test_attach_enrichment_sets_metadata():
    entity = make_entity()
    enrich = SimpleNamespace(
        summary="Does something important",
        usage_guide="Call with care",
        span_hash="abc123",
        symbol="demo.func",
    )

    _attach_enrichment_to_entity(entity, enrich)

    assert entity.metadata["summary"] == "Does something important"
    assert entity.metadata["usage_guide"] == "Call with care"
    assert entity.metadata["usage_snippet"] == "Call with care"
    assert entity.metadata["span_hash"] == "abc123"
    assert entity.metadata["symbol"] == "demo.func"


def test_attach_enrichment_handles_missing_optional_fields():
    entity = make_entity()
    enrich = SimpleNamespace(summary=None, usage_guide=None, span_hash="abc123", symbol=None)

    _attach_enrichment_to_entity(entity, enrich)

    # Only span_hash is applied when optional fields are missing.
    assert entity.metadata["span_hash"] == "abc123"
    assert "summary" not in entity.metadata
    assert "usage_guide" not in entity.metadata
