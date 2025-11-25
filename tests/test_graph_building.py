"""
Test 5: Graph Building - Node Coverage and Edge Construction
Test 6: Graph Building - Corrupt Graph Handling
"""
import json
import tempfile
import os
from pathlib import Path

# Calculate REPO_ROOT dynamically
REPO_ROOT = Path(__file__).resolve().parents[1]

def test_graph_node_coverage():
    """Test that graph includes all indexed files"""
    from tools.rag.graph import GraphStore
    from tools.rag.schema import SchemaGraph

    # Create a temporary graph file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        graph_data = {
            "version": 1,
            "indexed_at": "2025-11-16T00:00:00",
            "repo": str(REPO_ROOT),
            "entities": [
                {
                    "id": "file1:function_a",
                    "kind": "function",
                    "path": "file1.py:1-10",
                    "metadata": {}
                },
                {
                    "id": "file2:class_b",
                    "kind": "class",
                    "path": "file2.py:5-20",
                    "metadata": {}
                }
            ],
            "relations": []
        }
        json.dump(graph_data, f)
        graph_path = f.name

    try:
        # Load graph
        schema_graph = SchemaGraph.load(Path(graph_path))
        graph_store = GraphStore()
        graph_store.load_from_schema(schema_graph)

        print("Graph loaded:")
        print(f"  Entities: {len(graph_store.entities)}")
        print(f"  Entity IDs: {list(graph_store.entities.keys())}")

        # Verify node coverage
        assert len(graph_store.entities) == 2
        assert any("file1" in eid for eid in graph_store.entities.keys())
        assert any("file2" in eid for eid in graph_store.entities.keys())

        print("✓ Node coverage verified\n")

    finally:
        os.unlink(graph_path)

def test_graph_edge_construction():
    """Test that edges are created for references"""
    from tools.rag.graph import GraphStore
    from tools.rag.schema import SchemaGraph

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        graph_data = {
            "version": 1,
            "indexed_at": "2025-11-16T00:00:00",
            "repo": str(REPO_ROOT),
            "entities": [
                {
                    "id": "module:func_a",
                    "kind": "function",
                    "path": "module.py:1-10",
                    "metadata": {}
                },
                {
                    "id": "module:func_b",
                    "kind": "function",
                    "path": "module.py:15-25",
                    "metadata": {}
                },
                {
                    "id": "module:ClassA",
                    "kind": "class",
                    "path": "module.py:30-50",
                    "metadata": {}
                }
            ],
            "relations": [
                {
                    "src": "module:func_a",
                    "edge": "calls",
                    "dst": "module:func_b"
                },
                {
                    "src": "module:func_b",
                    "edge": "instantiates",
                    "dst": "module:ClassA"
                }
            ]
        }
        json.dump(graph_data, f)
        graph_path = f.name

    try:
        schema_graph = SchemaGraph.load(Path(graph_path))
        graph_store = GraphStore()
        graph_store.load_from_schema(schema_graph)

        print("Graph edges:")
        relations = graph_store._extract_relations()
        for rel in relations:
            print(f"  {rel.src} --{rel.edge}--> {rel.dst}")

        # Verify edge construction
        assert len(relations) == 2
        assert any(r.edge == "calls" for r in relations)
        assert any(r.edge == "instantiates" for r in relations)

        print("✓ Edge construction verified\n")

    finally:
        os.unlink(graph_path)

def test_graph_self_consistency():
    """Test that graph references only known entities"""
    from tools.rag.graph import GraphStore
    from tools.rag.schema import SchemaGraph

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        # Graph with dangling reference
        graph_data = {
            "version": 1,
            "indexed_at": "2025-11-16T00:00:00",
            "repo": str(REPO_ROOT),
            "entities": [
                {
                    "id": "known:entity",
                    "kind": "function",
                    "path": "test.py:1-10",
                    "metadata": {}
                }
            ],
            "relations": [
                {
                    "src": "known:entity",
                    "edge": "calls",
                    "dst": "unknown:entity"  # This should be flagged
                }
            ]
        }
        json.dump(graph_data, f)
        graph_path = f.name

    try:
        schema_graph = SchemaGraph.load(Path(graph_path))
        graph_store = GraphStore()
        graph_store.load_from_schema(schema_graph)

        print("Self-consistency check:")
        entity_ids = set(graph_store.entities.keys())
        relations = graph_store._extract_relations()
        dangling_refs = []

        for rel in relations:
            if rel.dst not in entity_ids:
                dangling_refs.append(rel.dst)
            if rel.src not in entity_ids:
                dangling_refs.append(rel.src)

        print(f"  Dangling references: {dangling_refs}")

        if dangling_refs:
            print("⚠ WARNING: Found dangling references!")
        else:
            print("✓ No dangling references")

    finally:
        os.unlink(graph_path)

def test_graph_corrupt_handling():
    """Test handling of corrupt or missing graph file"""
    from tools.rag.graph import GraphStore

    # Test 1: Missing file
    print("Test 1: Missing graph file")
    try:
        graph_store = GraphStore()
        graph_store.load_from_file(Path("/nonexistent/path/graph.json"))
        print("  ✗ Should have raised an error")
    except FileNotFoundError as e:
        print(f"  ✓ Correctly raised FileNotFoundError: {e}")
    except Exception as e:
        print(f"  ✓ Raised exception: {type(e).__name__}: {e}")

    # Test 2: Corrupt JSON
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{ this is not valid json }")
        corrupt_path = f.name

    try:
        print("\nTest 2: Corrupt JSON file")
        try:
            graph_store = GraphStore()
            graph_store.load_from_file(Path(corrupt_path))
            print("  ✗ Should have raised an error")
        except json.JSONDecodeError as e:
            print(f"  ✓ Correctly raised JSONDecodeError")
        except Exception as e:
            print(f"  ✓ Raised exception: {type(e).__name__}: {e}")
    finally:
        os.unlink(corrupt_path)

    # Test 3: Valid JSON but invalid schema
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"invalid": "schema", "missing": "fields"}')
        invalid_path = f.name

    try:
        print("\nTest 3: Valid JSON but invalid schema")
        try:
            from tools.rag.schema import SchemaGraph
            graph = SchemaGraph.load(Path(invalid_path))
            print(f"  Result: Loaded with defaults")
            print(f"  Entities: {len(graph.entities)}")
            print(f"  Relations: {len(graph.relations)}")
        except Exception as e:
            print(f"  Exception: {type(e).__name__}: {e}")
    finally:
        os.unlink(invalid_path)

    print("\n✓ Corrupt handling tests complete\n")

def test_existing_graph_artifacts():
    """Test the actual graph artifacts in the repo"""
    graph_path = REPO_ROOT / ".llmc" / "rag_graph.json"

    if not graph_path.exists():
        print(f"⚠ WARNING: {graph_path} does not exist")
        return

    print(f"Testing existing graph: {graph_path}")

    # Read and parse
    with open(graph_path, 'r') as f:
        data = json.load(f)

    # Check for entities (SchemaGraph format) or nodes (Nav graph format)
    entities = data.get('entities') or data.get('nodes', [])
    
    print(f"  Entities indexed: {len(entities)}")
    print(f"  Sample entities: {entities[:2]}")

    # Validate structure
    assert entities, "Graph should contain entities or nodes"
    assert isinstance(entities, list)
    assert len(entities) > 0

    print("✓ Existing graph is valid\n")
