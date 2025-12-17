import json
from pathlib import Path
import sys
import time

import pytest

# Try to import Database, if fails, skip tests
try:
    sys.path.append(".")
    from llmc.rag.database import Database

    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False

from llmc.docgen.graph_context import build_graph_context


class StubDatabase(Database):
    def __init__(self):
        pass

    def fetch_enrichment_by_span_hash(self, hash):
        return None


@pytest.fixture
def large_graph_file(tmp_path):
    graph_path = tmp_path / ".llmc" / "rag_graph.json"
    graph_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a graph with 50k entities
    # And add padding to make file large (~20MB+)
    entities = {}
    padding = "x" * 500
    for i in range(50000):
        entities[f"e{i}"] = {
            "file_path": f"src/file_{i % 100}.py",
            "name": f"Entity{i}",
            "kind": "function",
            "start_line": 10,
            "end_line": 20,
            "padding": padding,
        }

    graph_data = {"entities": entities, "relations": []}

    with open(graph_path, "w") as f:
        json.dump(graph_data, f)

    return graph_path


@pytest.mark.skipif(not HAS_DATABASE, reason="llmc.rag.database not available")
def test_graph_context_performance(tmp_path, large_graph_file):
    """Test that graph loading performance is acceptable."""
    # Mock database
    db = StubDatabase()

    repo_root = tmp_path

    # Measure time WITHOUT cache (old behavior)
    start_time = time.time()

    for i in range(5):
        # Access different files to ensure filtering logic runs
        file_path = Path(f"src/file_{i}.py")
        ctx = build_graph_context(repo_root, file_path, db)
        assert "no_graph_data" not in ctx  # Verify we actually found data

    end_time = time.time()
    uncached_duration = end_time - start_time
    avg_uncached = uncached_duration / 5

    print(f"\nWithout cache - Average time per call: {avg_uncached*1000:.2f} ms")

    # Measure time WITH cache (new behavior)
    from llmc.docgen.graph_context import load_graph_indices

    cached_graph = load_graph_indices(repo_root)

    start_time = time.time()

    for i in range(5):
        file_path = Path(f"src/file_{i}.py")
        ctx = build_graph_context(repo_root, file_path, db, cached_graph=cached_graph)
        assert "no_graph_data" not in ctx

    end_time = time.time()
    cached_duration = end_time - start_time
    avg_cached = cached_duration / 5

    print(f"With cache - Average time per call: {avg_cached*1000:.2f} ms")
    print(f"Speedup: {avg_uncached/avg_cached:.1f}x faster")

    # Cached version should be MUCH faster (< 10ms per call)
    if avg_cached > 0.01:
        pytest.fail(
            f"Cached performance too slow: {avg_cached*1000:.2f} ms per call (Expected: <10ms)"
        )
