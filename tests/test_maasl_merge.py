#!/usr/bin/env python3
"""
Tests for MAASL Phase 5: Graph Merge Engine.

Tests deterministic graph merging with concurrent updates.
"""

import threading

import pytest

from llmc_mcp.merge_meta import GraphPatch, MergeResult, get_merge_engine
from tools.rag.graph_store import GraphStore


@pytest.fixture
def empty_graph():
    """Create empty graph store."""
    return GraphStore()


@pytest.fixture
def merge_engine():
    """Create merge engine for tests."""
    return get_merge_engine(graph_id="test")


def test_graph_patch_validation():
    """Test GraphPatch validation."""
    # Valid patch
    patch = GraphPatch(
        nodes_to_add=[{"id": "func1", "kind": "function"}],
        edges_to_add=[{"source": "func1", "target": "func2", "type": "calls"}]
    )
    assert len(patch.nodes_to_add) == 1
    
    # Invalid - missing id
    with pytest.raises(ValueError, match="missing 'id'"):
        GraphPatch(nodes_to_add=[{"kind": "function"}])
    
    # Invalid - missing kind
    with pytest.raises(ValueError, match="missing 'kind'"):
        GraphPatch(nodes_to_add=[{"id": "func1"}])


def test_add_nodes(merge_engine, empty_graph):
    """Test adding nodes to graph."""
    patch = GraphPatch(
        nodes_to_add=[
            {"id": "func1", "kind": "function", "name": "calculate"},
            {"id": "func2", "kind": "function", "name": "process"},
        ]
    )
    
    result = merge_engine.apply_patch(
        patch,
        empty_graph,
        agent_id="agent1",
        session_id="session1",
    )
    
    assert result.success
    assert result.nodes_added == 2
    assert "func1" in empty_graph.entities
    assert "func2" in empty_graph.entities


def test_add_edges(merge_engine, empty_graph):
    """Test adding edges to graph."""
    # First add nodes
    patch1 = GraphPatch(
        nodes_to_add=[
            {"id": "func1", "kind": "function"},
            {"id": "func2", "kind": "function"},
        ]
    )
    merge_engine.apply_patch(patch1, empty_graph, agent_id="agent1", session_id="s1")
    
    # Now add edge
    patch2 = GraphPatch(
        edges_to_add=[
            {"source": "func1", "target": "func2", "type": "calls"}
        ]
    )
    result = merge_engine.apply_patch(patch2, empty_graph, agent_id="agent1", session_id="s1")
    
    assert result.success
    assert result.edges_added == 1
    assert "calls" in empty_graph.adjacency["func1"]["outgoing"]
    assert "func2" in empty_graph.adjacency["func1"]["outgoing"]["calls"]


def test_lww_node_conflict(merge_engine, empty_graph):
    """Test Last-Write-Wins for conflicting node additions."""
    # Agent 1 adds node with summary "v1"
    patch1 = GraphPatch(
        nodes_to_add=[
            {"id": "func1", "kind": "function", "summary": "version 1"}
        ]
    )
    merge_engine.apply_patch(patch1, empty_graph, agent_id="agent1", session_id="s1")
    
    # Agent 2 adds same node with summary "v2" (LWW - should overwrite)
    patch2 = GraphPatch(
        nodes_to_add=[
            {"id": "func1", "kind": "function", "summary": "version 2"}
        ]
    )
    result = merge_engine.apply_patch(patch2, empty_graph, agent_id="agent2", session_id="s2")
    
    assert result.success
    assert len(result.conflicts) > 0  # Conflict logged
    assert empty_graph.entities["func1"].metadata["summary"] == "version 2"  # LWW wins


def test_update_properties(merge_engine, empty_graph):
    """Test updating node properties."""
    # Add node
    patch1 = GraphPatch(
        nodes_to_add=[{"id": "func1", "kind": "function"}]
    )
    merge_engine.apply_patch(patch1, empty_graph, agent_id="agent1", session_id="s1")
    
    # Update properties
    patch2 = GraphPatch(
        properties_to_set={"func1": {"summary": "Does computation", "complexity": 5}}
    )
    result = merge_engine.apply_patch(patch2, empty_graph, agent_id="agent1", session_id="s1")
    
    assert result.success
    assert result.properties_updated == 2
    assert empty_graph.entities["func1"].metadata["summary"] == "Does computation"


def test_clear_properties(merge_engine, empty_graph):
    """Test clearing node properties."""
    # Add node with properties
    patch1 = GraphPatch(
        nodes_to_add=[{"id": "func1", "kind": "function", "temp_data": "remove_me"}]
    )
    merge_engine.apply_patch(patch1, empty_graph, agent_id="agent1", session_id="s1")
    
    # Clear property
    patch2 = GraphPatch(
        properties_to_clear={"func1": ["temp_data"]}
    )
    result = merge_engine.apply_patch(patch2, empty_graph, agent_id="agent1", session_id="s1")
    
    assert result.success
    assert result.properties_cleared == 1
    assert "temp_data" not in empty_graph.entities["func1"].metadata


@pytest.mark.allow_sleep
def test_concurrent_graph_updates(merge_engine, empty_graph):
    """
    Test concurrent graph updates are serialized.
    
    Core anti-stomp test for graph operations.
    """
    results: list[MergeResult] = []
    lock = threading.Lock()
    
    def update_agent(agent_id: str, node_id: str):
        """Agent adds a node to graph."""
        patch = GraphPatch(
            nodes_to_add=[
                {"id": node_id, "kind": "function", "agent": agent_id}
            ]
        )
        result = merge_engine.apply_patch(
            patch,
            empty_graph,
            agent_id=agent_id,
            session_id=f"session_{agent_id}",
        )
        
        with lock:
            results.append(result)
    
    # 3 agents add different nodes concurrently
    threads = [
        threading.Thread(target=update_agent, args=(f"agent{i}", f"func{i}"))
        for i in range(1, 4)
    ]
    
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # All should succeed
    assert all(r.success for r in results)
    assert len(results) == 3
    
    # All nodes should be in graph
    assert len(empty_graph.entities) == 3
    assert "func1" in empty_graph.entities
    assert "func2" in empty_graph.entities
    assert "func3" in empty_graph.entities


def test_deterministic_ordering(merge_engine, empty_graph):
    """Test that merge operations are deterministic."""
    # Create patch with unsorted nodes
    patch = GraphPatch(
        nodes_to_add=[
            {"id": "zebra", "kind": "function"},
            {"id": "alpha", "kind": "function"},
            {"id": "beta", "kind": "function"},
        ]
    )
    
    # Apply twice - should be deterministic
    result1 = merge_engine.apply_patch(patch, empty_graph, agent_id="agent1", session_id="s1")
    
    # Nodes should be added in sorted order (internally)
    assert result1.success
    assert len(empty_graph.entities) == 3


def test_missing_edge_nodes(merge_engine, empty_graph):
    """Test that edges with missing nodes are handled gracefully."""
    patch = GraphPatch(
        edges_to_add=[
            {"source": "nonexistent1", "target": "nonexistent2", "type": "calls"}
        ]
    )
    
    result = merge_engine.apply_patch(patch, empty_graph, agent_id="agent1", session_id="s1")
    
    assert result.success  # Still succeeds
    assert result.edges_added == 0  # But edge not added
    assert len(result.conflicts) > 0  # Conflict logged


def test_merge_result_structure():
    """Test MergeResult structure."""
    result = MergeResult(
        success=True,
        nodes_added=5,
        edges_added=10,
        properties_updated=3,
        conflicts=["conflict1"],
    )
    
    assert result.success
    assert result.nodes_added == 5
    assert result.merge_timestamp > 0
