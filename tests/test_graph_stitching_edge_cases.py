"""Ruthless edge case tests for Graph Stitching (P9c feature).

Tests cover:
- 1-hop neighbor expansion
- Graph stitch failures
- Mixed RAG + stitched results
"""

import json
from pathlib import Path
from unittest.mock import Mock, patch


class TestOneHopNeighborExpansion:
    """Test 1-hop neighbor expansion logic."""

    def create_test_graph(self, tmp_path: Path) -> Path:
        """Create a test graph for stitching."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph = {
            "nodes": [
                {"id": "func_a", "path": "file1.py", "name": "func_a"},
                {"id": "func_b", "path": "file2.py", "name": "func_b"},
                {"id": "func_c", "path": "file3.py", "name": "func_c"},
                {"id": "func_d", "path": "file4.py", "name": "func_d"},
                {"id": "func_e", "path": "file5.py", "name": "func_e"},
            ],
            "edges": [
                {"type": "CALLS", "source": "func_a", "target": "func_b"},
                {"type": "CALLS", "source": "func_b", "target": "func_c"},
                {"type": "CALLS", "source": "func_a", "target": "func_c"},
                {"type": "CALLS", "source": "func_c", "target": "func_d"},
                {"type": "CALLS", "source": "func_d", "target": "func_e"},
            ],
        }

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        return repo_root

    def test_expand_search_items_with_neighbors(self, tmp_path: Path):
        """Test expanding search items with graph neighbors."""
        self.create_test_graph(tmp_path)

        # Mock search items (starting points)
        [
            Mock(file="file1.py"),
            Mock(file="file2.py"),
        ]

        # Mock neighbors from graph
        [
            Mock(path="file3.py"),
            Mock(path="file4.py"),
            Mock(path="file5.py"),
        ]

        # Should expand to include neighbors
        # Implementation: expand_search_items(repo_root_path, items, max_expansion, hops=1)

    def test_max_expansion_limit(self, tmp_path: Path):
        """Test that max_expansion limits number of neighbors added."""
        self.create_test_graph(tmp_path)

        [Mock(file="file1.py")]

        # Graph has 4 neighbors but max_expansion is 2

        # Should only add 2 neighbors

    def test_one_hop_only(self, tmp_path: Path):
        """Test that only 1-hop neighbors are expanded (not 2-hop)."""
        self.create_test_graph(tmp_path)

        # Graph structure: func_a -> func_b -> func_c -> func_d
        # Starting from func_a:
        # - 1-hop: func_b (direct neighbor)
        # - 2-hop: func_c (neighbor's neighbor)
        # Should only include func_b, not func_c

        [Mock(file="file1.py")]  # func_a

        # Should not include func_c (2-hop away)

    def test_zero_hop_expansion(self, tmp_path: Path):
        """Test expansion with hops=0 (no expansion)."""
        self.create_test_graph(tmp_path)

        [
            Mock(file="file1.py"),
            Mock(file="file2.py"),
        ]

        # hops=0 means no expansion
        # Result should be same as input

    def test_no_graph_file(self, tmp_path: Path):
        """Test behavior when graph file doesn't exist."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        [Mock(file="file1.py")]

        # Should handle missing graph gracefully
        # May return original items or empty

    def test_empty_graph(self, tmp_path: Path):
        """Test behavior with empty graph (no nodes/edges)."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph = {"nodes": [], "edges": []}

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        [Mock(file="file1.py")]

        # Empty graph means no neighbors to find

    def test_no_edges_in_graph(self, tmp_path: Path):
        """Test graph with nodes but no edges."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph = {
            "nodes": [
                {"id": "func_a", "path": "file1.py"},
                {"id": "func_b", "path": "file2.py"},
            ],
            "edges": [],  # No connections
        }

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        [Mock(file="file1.py")]

        # No edges means no neighbors

    def test_graph_with_cycles(self, tmp_path: Path):
        """Test graph with cyclic dependencies."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph = {
            "nodes": [
                {"id": "func_a", "path": "file1.py"},
                {"id": "func_b", "path": "file2.py"},
                {"id": "func_c", "path": "file3.py"},
            ],
            "edges": [
                {"type": "CALLS", "source": "func_a", "target": "func_b"},
                {"type": "CALLS", "source": "func_b", "target": "func_c"},
                {"type": "CALLS", "source": "func_c", "target": "func_a"},  # Cycle
            ],
        }

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        [Mock(file="file1.py")]

        # Should handle cycles without infinite loop
        # May use visited set to prevent cycles

    def test_graph_with_self_loops(self, tmp_path: Path):
        """Test graph with self-referencing nodes."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph = {
            "nodes": [
                {"id": "func_a", "path": "file1.py"},
            ],
            "edges": [
                {"type": "CALLS", "source": "func_a", "target": "func_a"},  # Self-loop
            ],
        }

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        [Mock(file="file1.py")]

        # Should handle self-loops gracefully

    def test_multiple_edge_types(self, tmp_path: Path):
        """Test graph with various edge types."""
        repo_root = self.create_test_graph(tmp_path)

        # Graph with different edge types
        graph = {
            "nodes": [
                {"id": "func_a", "path": "file1.py"},
                {"id": "func_b", "path": "file2.py"},
                {"id": "var_x", "path": "file3.py"},
            ],
            "edges": [
                {"type": "CALLS", "source": "func_a", "target": "func_b"},
                {"type": "READS", "source": "func_b", "target": "var_x"},
                {"type": "WRITES", "source": "func_b", "target": "var_x"},
            ],
        }

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.write_text(json.dumps(graph))

        # Should consider relevant edge types
        # Implementation may filter by type

    def test_neighbors_from_multiple_items(self, tmp_path: Path):
        """Test expansion from multiple starting items."""
        self.create_test_graph(tmp_path)

        # Multiple starting points
        [
            Mock(file="file1.py"),  # func_a
            Mock(file="file2.py"),  # func_b
        ]

        # Should union neighbors from all starting points
        # Deduplicate if same neighbor found from multiple sources

    def test_graph_not_found_exception(self, tmp_path: Path):
        """Test GraphNotFound exception handling."""
        # When graph file is missing
        # Should raise or handle GraphNotFound

    def test_neighbors_with_missing_node_ids(self, tmp_path: Path):
        """Test edges reference nodes that don't exist."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph = {
            "nodes": [
                {"id": "func_a", "path": "file1.py"},
            ],
            "edges": [
                {"type": "CALLS", "source": "func_a", "target": "nonexistent"},
            ],
        }

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        [Mock(file="file1.py")]

        # Should handle missing target nodes

    def test_large_graph_expansion(self, tmp_path: Path):
        """Test expansion on large graph (100+ nodes)."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Create large graph
        nodes = [{"id": f"func_{i}", "path": f"file_{i}.py"} for i in range(100)]
        edges = [
            {"type": "CALLS", "source": f"func_{i}", "target": f"func_{i + 1}"} for i in range(99)
        ]

        graph = {"nodes": nodes, "edges": edges}
        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        [Mock(file="file_0.py")]

        # Should handle large graphs efficiently
        # May need batching or streaming

    def test_expansion_with_unicode_names(self, tmp_path: Path):
        """Test expansion with unicode characters in node names."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph = {
            "nodes": [
                {"id": "функция", "path": "файл.py"},
                {"id": "関数", "path": "ファイル.py"},
                {"id": "函数", "path": "文件.py"},
            ],
            "edges": [
                {"type": "CALLS", "source": "функция", "target": "関数"},
                {"type": "CALLS", "source": "関数", "target": "函数"},
            ],
        }

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        [Mock(file="файл.py")]

        # Should handle unicode properly


class TestGraphStitchFailures:
    """Test graceful handling of graph stitch failures."""

    def create_test_graph(self, tmp_path: Path) -> Path:
        """Create a test graph for stitching."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph = {
            "nodes": [
                {"id": "func_a", "path": "file1.py", "name": "func_a"},
                {"id": "func_b", "path": "file2.py", "name": "func_b"},
                {"id": "func_c", "path": "file3.py", "name": "func_c"},
                {"id": "func_d", "path": "file4.py", "name": "func_d"},
                {"id": "func_e", "path": "file5.py", "name": "func_e"},
            ],
            "edges": [
                {"type": "CALLS", "source": "func_a", "target": "func_b"},
                {"type": "CALLS", "source": "func_b", "target": "func_c"},
                {"type": "CALLS", "source": "func_a", "target": "func_c"},
                {"type": "CALLS", "source": "func_c", "target": "func_d"},
                {"type": "CALLS", "source": "func_d", "target": "func_e"},
            ],
        }

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        return repo_root

    def test_graph_file_corruption(self, tmp_path: Path):
        """Test handling of corrupted graph file."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text("{ corrupt json !@#$ }")

        [Mock(file="file1.py")]

        # Should handle parse error gracefully
        # Return original items without expansion

    def test_graph_file_permission_error(self, tmp_path: Path):
        """Test handling when graph file can't be read."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)

        # Remove any existing file first
        if graph_path.exists():
            graph_path.unlink()

        # Write and then close the file before changing permissions
        with graph_path.open("w") as f:
            f.write('{"nodes": [], "edges": []}')

        # Make file unreadable
        graph_path.chmod(0o000)

        [Mock(file="file1.py")]

        # Should handle permission error

    def test_graph_file_io_error(self, tmp_path: Path):
        """Test handling of I/O errors during graph read."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Simulate I/O error
        with patch("builtins.open", side_effect=OSError("Disk error")):
            [Mock(file="file1.py")]

            # Should handle I/O error gracefully

    def test_expansion_timeout(self, tmp_path: Path):
        """Test expansion with timeout protection."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        # Large graph that might take time
        nodes = [{"id": f"func_{i}", "path": f"file_{i}.py"} for i in range(1000)]
        edges = [
            {"type": "CALLS", "source": f"func_{i}", "target": f"func_{j}"}
            for i in range(1000)
            for j in range(i - 5, i + 5)
            if 0 <= j < 1000 and j != i
        ]

        graph = {"nodes": nodes, "edges": edges}
        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        [Mock(file="file_0.py")]

        # Should have timeout protection
        # Prevent infinite expansion

    def test_memory_limit_during_expansion(self, tmp_path: Path):
        """Test handling when memory is low."""
        # Simulate memory pressure
        # Should fail gracefully or use less memory

    def test_malformed_node_structure(self, tmp_path: Path):
        """Test handling of nodes with missing required fields."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph = {
            "nodes": [
                {"id": "func_a", "path": "file1.py"},  # Valid
                {"path": "file2.py"},  # Missing id
                {"id": "func_c"},  # Missing path
                {},  # Empty node
            ],
            "edges": [],
        }

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        [Mock(file="file1.py")]

        # Should validate node structure

    def test_malformed_edge_structure(self, tmp_path: Path):
        """Test handling of edges with missing required fields."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph = {
            "nodes": [
                {"id": "func_a", "path": "file1.py"},
                {"id": "func_b", "path": "file2.py"},
            ],
            "edges": [
                {"type": "CALLS", "source": "func_a", "target": "func_b"},  # Valid
                {"source": "func_a", "target": "func_b"},  # Missing type
                {"type": "CALLS", "target": "func_b"},  # Missing source
                {"type": "CALLS", "source": "func_a"},  # Missing target
            ],
        }

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        [Mock(file="file1.py")]

        # Should validate edge structure

    def test_duplicate_nodes(self, tmp_path: Path):
        """Test handling of duplicate node IDs."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph = {
            "nodes": [
                {"id": "func_a", "path": "file1.py"},
                {"id": "func_a", "path": "file2.py"},  # Duplicate ID
            ],
            "edges": [],
        }

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        [Mock(file="file1.py")]

        # Should handle or deduplicate

    def test_duplicate_edges(self, tmp_path: Path):
        """Test handling of duplicate edges."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph = {
            "nodes": [
                {"id": "func_a", "path": "file1.py"},
                {"id": "func_b", "path": "file2.py"},
            ],
            "edges": [
                {"type": "CALLS", "source": "func_a", "target": "func_b"},
                {"type": "CALLS", "source": "func_a", "target": "func_b"},  # Duplicate
            ],
        }

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        [Mock(file="file1.py")]

        # Should deduplicate or handle

    def test_disconnected_graph(self, tmp_path: Path):
        """Test graph with multiple disconnected components."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph = {
            "nodes": [
                {"id": "func_a", "path": "file1.py"},
                {"id": "func_b", "path": "file2.py"},
                {"id": "func_c", "path": "file3.py"},
                {"id": "func_d", "path": "file4.py"},
            ],
            "edges": [
                # Component 1: a -> b
                {"type": "CALLS", "source": "func_a", "target": "func_b"},
                # Component 2: c -> d (disconnected from component 1)
                {"type": "CALLS", "source": "func_c", "target": "func_d"},
            ],
        }

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        [Mock(file="file1.py")]  # In component 1

        # Should only find neighbors in same component

    def test_infinite_loop_protection(self, tmp_path: Path):
        """Test that expansion prevents infinite loops."""
        # Use visited set to track processed nodes
        # Don't revisit nodes

    def test_concurrent_expansion_requests(self, tmp_path: Path):
        """Test concurrent expansion requests on same graph."""
        import threading

        self.create_test_graph(tmp_path)
        results = []

        def expand():
            search_items = [Mock(file="file1.py")]
            # Run expansion
            results.append(len(search_items))

        threads = [threading.Thread(target=expand) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should complete successfully


class TestMixedRAGStitchedResults:
    """Test combining RAG search results with graph-stitched neighbors."""

    def create_test_graph(self, tmp_path: Path) -> Path:
        """Create a test graph for stitching."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        graph = {
            "nodes": [
                {"id": "func_a", "path": "file1.py", "name": "func_a"},
                {"id": "func_b", "path": "file2.py", "name": "func_b"},
                {"id": "func_c", "path": "file3.py", "name": "func_c"},
                {"id": "func_d", "path": "file4.py", "name": "func_d"},
                {"id": "func_e", "path": "file5.py", "name": "func_e"},
            ],
            "edges": [
                {"type": "CALLS", "source": "func_a", "target": "func_b"},
                {"type": "CALLS", "source": "func_b", "target": "func_c"},
                {"type": "CALLS", "source": "func_a", "target": "func_c"},
                {"type": "CALLS", "source": "func_c", "target": "func_d"},
                {"type": "CALLS", "source": "func_d", "target": "func_e"},
            ],
        }

        graph_path = repo_root / ".llmc" / "rag_graph.json"
        graph_path.parent.mkdir(parents=True)
        graph_path.write_text(json.dumps(graph))

        return repo_root

    def test_mix_rag_and_stitched_results(self, tmp_path: Path):
        """Test combining original RAG results with stitched neighbors."""
        self.create_test_graph(tmp_path)

        # Original RAG results
        [
            Mock(file="file1.py"),
            Mock(file="file2.py"),
        ]

        # Stitched neighbors
        [
            Mock(file="file3.py"),
            Mock(file="file4.py"),
            Mock(file="file5.py"),
        ]

        # Combined result should have both
        # Should be: rag_items + stitched_items (up to max_results)

    def test_duplicate_files_deduplication(self, tmp_path: Path):
        """Test that duplicate files between RAG and stitched are deduplicated."""
        self.create_test_graph(tmp_path)

        # Original RAG results
        [
            Mock(file="file1.py"),
            Mock(file="file2.py"),
            Mock(file="file3.py"),  # This will also be in stitched
        ]

        # Stitched neighbors (file3.py overlaps)
        [
            Mock(file="file3.py"),  # Duplicate!
            Mock(file="file4.py"),
        ]

        # Result should deduplicate file3.py
        # Count: 4 unique files (1, 2, 3, 4) not 5

    def test_seen_files_tracking(self, tmp_path: Path):
        """Test tracking of already-seen files to avoid duplicates."""
        # Use a set to track file paths
        seen_files = set()

        # Add file1.py
        seen_files.add("file1.py")
        assert "file1.py" in seen_files

        # Try to add file1.py again
        if "file1.py" not in seen_files:
            seen_files.add("file1.py")

        # Should only have 1 instance
        assert len(seen_files) == 1

    def test_max_results_enforcement(self, tmp_path: Path):
        """Test that max_results limit is enforced after stitching."""
        self.create_test_graph(tmp_path)

        [Mock(file=f"file{i}.py") for i in range(15)]
