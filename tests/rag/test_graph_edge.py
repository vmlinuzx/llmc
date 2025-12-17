import pytest

from llmc.rag.graph.edge import GraphEdge
from llmc.rag.graph.edge_types import EdgeType

# AC-1 Tests


def test_edge_creation():
    """Test basic dataclass creation."""
    edge = GraphEdge(
        source_id="src1",
        target_id="tgt1",
        edge_type="REFERENCES",
        score=0.8,
        match_text="reference to",
    )
    assert edge.source_id == "src1"
    assert edge.target_id == "tgt1"
    assert edge.edge_type == "REFERENCES"
    assert edge.score == 0.8
    assert edge.match_text == "reference to"
    assert edge.pattern_id is None
    assert edge.llm_trace_id is None
    assert edge.model_name is None


def test_is_high_confidence_above_threshold():
    """Test is_high_confidence returns True when score >= threshold."""
    edge = GraphEdge("s", "t", "r", 0.8)
    assert edge.is_high_confidence(0.7) is True
    assert edge.is_high_confidence(0.8) is True


def test_is_high_confidence_below_threshold():
    """Test is_high_confidence returns False when score < threshold."""
    edge = GraphEdge("s", "t", "r", 0.6)
    assert edge.is_high_confidence(0.7) is False


def test_is_llm_extracted_true():
    """Test is_llm_extracted returns True when llm_trace_id is set."""
    edge = GraphEdge("s", "t", "r", 0.9, llm_trace_id="trace-123")
    assert edge.is_llm_extracted() is True


def test_is_llm_extracted_false():
    """Test is_llm_extracted returns False when llm_trace_id is None."""
    edge = GraphEdge("s", "t", "r", 0.9, llm_trace_id=None)
    assert edge.is_llm_extracted() is False


# AC-2 Tests


def test_edge_type_values():
    """Test all enum values are strings."""
    assert isinstance(EdgeType.REFERENCES.value, str)
    assert isinstance(EdgeType.REQUIRES.value, str)
    assert isinstance(EdgeType.RELATED_TO.value, str)
    assert isinstance(EdgeType.SUPERSEDES.value, str)
    assert isinstance(EdgeType.WARNS_ABOUT.value, str)

    assert EdgeType.REFERENCES == "REFERENCES"


def test_edge_type_membership():
    """Test can check if string is valid edge type."""
    # Since it inherits from str and Enum, we can check membership in the class
    assert "REFERENCES" in [e.value for e in EdgeType]
    assert "INVALID" not in [e.value for e in EdgeType]

    # Or by instantiation
    assert EdgeType("REFERENCES") == EdgeType.REFERENCES
    with pytest.raises(ValueError):
        EdgeType("INVALID")
