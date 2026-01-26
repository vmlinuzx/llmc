
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


# =============================================================================
# Tests for dict-based resolution (rag_nav compatibility)
# =============================================================================

from llmc.symbol_resolver import (
    resolve_symbol_in_nodes,
    resolve_symbol_in_nodes_best,
)


@pytest.fixture
def mock_nodes() -> list[dict]:
    """Provides mock node dicts for testing (simulates rag_graph.json format)."""
    return [
        {"name": "Router", "kind": "class", "path": "app/router.py"},
        {"name": "EnrichmentPipeline", "kind": "class", "path": "app/pipelines.py"},
        {"name": "run_pipeline", "kind": "function", "path": "app/pipelines.py"},
        {"name": "DeterministicRouter", "kind": "class", "path": "app/router.py"},
        {"name": "enrich_data", "kind": "function", "path": "app/enrichment.py"},
        {"id": "class:Database", "kind": "class", "path": "app/db.py"},  # Uses 'id' instead of 'name'
    ]


def test_nodes_exact_match(mock_nodes):
    """Test exact match on node dicts."""
    matches = resolve_symbol_in_nodes("Router", mock_nodes)
    assert len(matches) > 0
    assert matches[0].node["name"] == "Router"
    assert matches[0].score == 1.0
    assert matches[0].match_type == "exact"


def test_nodes_case_insensitive_match(mock_nodes):
    """Test case-insensitive match on node dicts."""
    matches = resolve_symbol_in_nodes("router", mock_nodes)
    assert len(matches) > 0
    assert matches[0].node["name"] == "Router"
    assert matches[0].score == 0.9
    assert matches[0].match_type == "case-insensitive"


def test_nodes_suffix_match(mock_nodes):
    """Test suffix match on node dicts."""
    matches = resolve_symbol_in_nodes("Pipeline", mock_nodes)
    assert len(matches) > 0
    assert matches[0].node["name"] == "EnrichmentPipeline"
    assert matches[0].score == 0.7
    assert matches[0].match_type == "suffix"


def test_nodes_contains_match(mock_nodes):
    """Test contains match on node dicts."""
    matches = resolve_symbol_in_nodes("enrich", mock_nodes)
    # Should find EnrichmentPipeline (class) and enrich_data (function)
    assert len(matches) == 2
    # Class should be ranked higher due to kind priority
    assert matches[0].node["name"] == "EnrichmentPipeline"
    assert matches[0].score == 0.5
    assert matches[1].node["name"] == "enrich_data"
    assert matches[1].score == 0.5


def test_nodes_with_id_key(mock_nodes):
    """Test resolution when node uses 'id' key instead of 'name'."""
    # The Database node uses 'id' instead of 'name'
    matches = resolve_symbol_in_nodes("database", mock_nodes)
    assert len(matches) > 0
    # Should find via fallback to 'id' key with prefix stripping
    found_db = any(m.node.get("id") == "class:Database" for m in matches)
    assert found_db, f"Database not found in matches: {matches}"


def test_nodes_no_match(mock_nodes):
    """Test no matches for unknown symbol."""
    matches = resolve_symbol_in_nodes("NonExistentSymbol", mock_nodes)
    assert len(matches) == 0


def test_nodes_empty_inputs():
    """Test graceful handling of empty inputs."""
    assert resolve_symbol_in_nodes("", []) == []
    assert resolve_symbol_in_nodes("symbol", []) == []
    assert resolve_symbol_in_nodes("", [{"name": "Foo"}]) == []


def test_nodes_best_success(mock_nodes):
    """Test resolve_symbol_in_nodes_best returns the top node."""
    node = resolve_symbol_in_nodes_best("router", mock_nodes)
    assert node is not None
    assert node["name"] == "Router"


def test_nodes_best_no_match(mock_nodes):
    """Test resolve_symbol_in_nodes_best returns None for no matches."""
    node = resolve_symbol_in_nodes_best("NonExistentSymbol", mock_nodes)
    assert node is None


def test_nodes_prefixed_id():
    """Test that prefixed IDs like 'class:Router' are handled correctly."""
    nodes = [
        {"id": "class:Router", "kind": "class"},
        {"id": "func:run", "kind": "function"},
    ]
    matches = resolve_symbol_in_nodes("router", nodes, name_key="id")
    assert len(matches) > 0
    assert matches[0].node["id"] == "class:Router"
    assert matches[0].score == 0.9  # case-insensitive match


def test_nodes_kind_priority():
    """Test that classes are ranked higher than functions with same score."""
    nodes = [
        {"name": "process_data", "kind": "function"},
        {"name": "Process", "kind": "class"},
    ]
    # Both match "process" as contains
    matches = resolve_symbol_in_nodes("process", nodes)
    assert len(matches) == 2
    # Class should be first due to kind priority
    assert matches[0].node["kind"] == "class"
    assert matches[1].node["kind"] == "function"

