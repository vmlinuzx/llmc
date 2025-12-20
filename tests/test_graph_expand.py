"""
Unit tests for Graph Expansion (Phase 2).
"""
import pytest
from unittest.mock import MagicMock, patch
from llmc.rag.graph_expand import GraphExpander, expand_with_graph
from llmc.rag.graph_index import GraphIndices, GraphNotFound

@pytest.fixture
def mock_indices():
    indices = MagicMock(spec=GraphIndices)
    # symbol -> files (upstream/where-used)
    indices.symbol_to_files = {
        "func_a": {"file_b.py", "file_c.py"},
        "class_x": {"file_y.py"},
        "hub_node": {f"client_{i}.py" for i in range(100)},
    }
    # symbol -> callee files (downstream)
    indices.symbol_to_callee_files = {
        "func_a": {"lib_z.py"},
        "class_x": set(),
        "orphaned": set(),
    }
    return indices

def test_expander_basic(mock_indices):
    expander = GraphExpander(mock_indices, decay_factor=0.5, top_n_expand=5)
    
    candidates = [
        {"file_path": "file_a.py", "symbol": "func_a", "score": 10.0}
    ]
    
    expanded = expander.expand_candidates(candidates)
    
    # Expect: file_a.py (orig) + file_b.py, file_c.py, lib_z.py (neighbors)
    assert len(expanded) == 4
    
    # check scores
    neighbor_score = 10.0 * 0.5
    neighbor_paths = {c["file_path"] for c in expanded[1:]}
    assert "file_b.py" in neighbor_paths
    assert "lib_z.py" in neighbor_paths
    
    for c in expanded[1:]:
        assert c["score"] == neighbor_score
        assert c["_expansion_type"] == "graph_neighbor"
        assert c["_expansion_source"] == "file_a.py"

def test_expander_hub_penalty(mock_indices):
    expander = GraphExpander(mock_indices, hub_threshold=10)
    
    candidates = [
        {"file_path": "hub.py", "symbol": "hub_node", "score": 10.0}
    ]
    
    expanded = expander.expand_candidates(candidates)
    
    # Should skip expansion because hub_node has 100 neighbors
    assert len(expanded) == 1
    assert expanded[0]["file_path"] == "hub.py"

def test_expander_empty_candidates(mock_indices):
    expander = GraphExpander(mock_indices)
    assert expander.expand_candidates([]) == []

def test_expander_deduplication(mock_indices):
    expander = GraphExpander(mock_indices)
    
    # file_b.py is already a candidate, and also a neighbor of func_a
    candidates = [
        {"file_path": "file_a.py", "symbol": "func_a", "score": 10.0},
        {"file_path": "file_b.py", "symbol": "func_b", "score": 8.0}
    ]
    
    expanded = expander.expand_candidates(candidates)
    
    # Neighbors of func_a: file_b.py, file_c.py, lib_z.py
    # file_b.py is already in candidates, so should not be added again as a neighbor
    
    paths = [c["file_path"] for c in expanded]
    assert paths.count("file_b.py") == 1
    
    # file_c.py and lib_z.py should be added
    assert "file_c.py" in paths
    assert "lib_z.py" in paths

def test_expand_with_graph_no_graph():
    candidates = [{"file_path": "a.py"}]
    config = {"rag": {"graph": {"enable_expansion": True}}}
    
    with patch("llmc.rag.graph_expand.load_indices", side_effect=GraphNotFound("missing")):
        result = expand_with_graph(candidates, "repo_root", config)
        assert result == candidates

def test_expand_with_graph_disabled():
    candidates = [{"file_path": "a.py"}]
    config = {"rag": {"graph": {"enable_expansion": False}}}
    
    # Should not even try to load indices
    with patch("llmc.rag.graph_expand.load_indices") as mock_load:
        result = expand_with_graph(candidates, "repo_root", config)
        assert result == candidates
        mock_load.assert_not_called()
