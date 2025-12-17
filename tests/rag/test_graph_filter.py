import pytest

from llmc.rag.graph.edge import GraphEdge
from llmc.rag.graph.filter import (
    filter_edges_by_confidence,
    filter_edges_by_type,
    filter_llm_edges,
)


@pytest.fixture
def sample_edges():
    return [
        GraphEdge("s1", "t1", "REFERENCES", 0.9),
        GraphEdge("s2", "t2", "REQUIRES", 0.5),
        GraphEdge("s3", "t3", "RELATED_TO", 0.8, llm_trace_id="trace1"),
        GraphEdge("s4", "t4", "REFERENCES", 0.6),
    ]


def test_filter_by_confidence_keeps_high(sample_edges):
    """Test filtering keeps edges above or equal to threshold."""
    filtered = filter_edges_by_confidence(sample_edges, 0.8)
    assert len(filtered) == 2
    assert filtered[0].score == 0.9
    assert filtered[1].score == 0.8


def test_filter_by_confidence_removes_low(sample_edges):
    """Test filtering removes edges below threshold."""
    filtered = filter_edges_by_confidence(sample_edges, 0.95)
    assert len(filtered) == 0


def test_filter_by_type_single(sample_edges):
    """Test filtering by a single type."""
    filtered = filter_edges_by_type(sample_edges, {"REQUIRES"})
    assert len(filtered) == 1
    assert filtered[0].edge_type == "REQUIRES"


def test_filter_by_type_multiple(sample_edges):
    """Test filtering by multiple types."""
    filtered = filter_edges_by_type(sample_edges, {"REFERENCES", "RELATED_TO"})
    assert len(filtered) == 3
    types = {e.edge_type for e in filtered}
    assert "REFERENCES" in types
    assert "RELATED_TO" in types
    assert "REQUIRES" not in types


def test_filter_llm_edges(sample_edges):
    """Test filtering only LLM extracted edges."""
    filtered = filter_llm_edges(sample_edges)
    assert len(filtered) == 1
    assert filtered[0].llm_trace_id == "trace1"
