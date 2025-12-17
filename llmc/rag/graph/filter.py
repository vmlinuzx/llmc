
from llmc.rag.graph.edge import GraphEdge


def filter_edges_by_confidence(edges: list[GraphEdge], threshold: float) -> list[GraphEdge]:
    """Filter edges that meet or exceed confidence threshold."""
    return [e for e in edges if e.score >= threshold]

def filter_edges_by_type(edges: list[GraphEdge], edge_types: set[str]) -> list[GraphEdge]:
    """Filter edges by allowed types."""
    return [e for e in edges if e.edge_type in edge_types]

def filter_llm_edges(edges: list[GraphEdge]) -> list[GraphEdge]:
    """Return only edges that were LLM-extracted."""
    return [e for e in edges if e.is_llm_extracted()]
