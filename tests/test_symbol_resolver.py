
import pytest
from llmc.rag.schema import Entity, SchemaGraph
from llmc.symbol_resolver import (
    resolve_symbol,
    resolve_symbol_best,
)


@pytest.fixture
def mock_graph() -> SchemaGraph:
    """Provides a mock SchemaGraph for testing."""
    entities = [
        Entity(id="class:Router", kind="class", path="app/router.py"),
        Entity(
            id="class:EnrichmentPipeline",
            kind="class",
            path="app/pipelines.py",
        ),
        Entity(
            id="func:run_pipeline",
            kind="function",
            path="app/pipelines.py",
        ),
        Entity(
            id="class:DeterministicRouter",
            kind="class",
            path="app/router.py",
        ),
        Entity(
            id="func:enrich_data",
            kind="function",
            path="app/enrichment.py",
        ),
    ]
    return SchemaGraph(entities=entities)


def test_exact_match(mock_graph):
    """Test that an exact symbol match gets the highest score."""
    matches = resolve_symbol("Router", mock_graph)
    assert len(matches) > 0
    assert matches[0].entity.id == "class:Router"
    assert matches[0].score == 1.0
    assert matches[0].match_type == "exact"


def test_case_insensitive_match(mock_graph):
    """Test that a case-insensitive match works and scores correctly."""
    matches = resolve_symbol("router", mock_graph)
    assert len(matches) > 0
    # First result should be the case-insensitive match for Router
    assert matches[0].entity.id == "class:Router"
    assert matches[0].score == 0.9
    assert matches[0].match_type == "case-insensitive"


def test_suffix_match(mock_graph):
    """Test that a suffix match works and scores correctly."""
    matches = resolve_symbol("Pipeline", mock_graph)
    assert len(matches) > 0
    assert matches[0].entity.id == "class:EnrichmentPipeline"
    assert matches[0].score == 0.7
    assert matches[0].match_type == "suffix"


def test_contains_match(mock_graph):
    """Test that a contains match works and scores correctly."""
    matches = resolve_symbol("enrich", mock_graph)
    # Should find EnrichmentPipeline (class) and enrich_data (function)
    assert len(matches) == 2
    # The class should be ranked higher due to kind priority
    assert matches[0].entity.id == "class:EnrichmentPipeline"
    assert matches[0].score == 0.5
    assert matches[0].match_type == "contains"
    assert matches[1].entity.id == "func:enrich_data"
    assert matches[1].score == 0.5
    assert matches[1].match_type == "contains"


def test_no_match(mock_graph):
    """Test that no matches are returned for a symbol not in the graph."""
    matches = resolve_symbol("NonExistentSymbol", mock_graph)
    assert len(matches) == 0


def test_multiple_matches_ranking(mock_graph):
    """Test that multiple matches are ranked correctly by score and kind."""
    # "router" will match:
    # - "Router" (case-insensitive, score 0.9, class)
    # - "DeterministicRouter" (suffix, score 0.7, class)
    matches = resolve_symbol("router", mock_graph)
    assert len(matches) == 2
    assert matches[0].entity.id == "class:Router"
    assert matches[0].score == 0.9
    assert matches[1].entity.id == "class:DeterministicRouter"
    assert matches[1].score == 0.7


def test_resolve_symbol_best_success(mock_graph):
    """Test that resolve_symbol_best returns the top entity."""
    entity = resolve_symbol_best("router", mock_graph)
    assert entity is not None
    assert entity.id == "class:Router"


def test_resolve_symbol_best_no_match(mock_graph):
    """Test that resolve_symbol_best returns None for no matches."""
    entity = resolve_symbol_best("NonExistentSymbol", mock_graph)
    assert entity is None


def test_empty_query_and_graph():
    """Test that the resolver handles empty inputs gracefully."""
    empty_graph = SchemaGraph(entities=[])
    # Empty symbol
    assert resolve_symbol("", empty_graph) == []
    # Empty graph
    assert resolve_symbol("symbol", empty_graph) == []
    # Both empty
    assert resolve_symbol("", empty_graph) == []
    # Empty symbol with graph
    assert resolve_symbol("", SchemaGraph(entities=[Entity(id="foo", kind="bar", path="dummy.py")])) == []
