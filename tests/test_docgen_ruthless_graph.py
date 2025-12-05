from pathlib import Path

import pytest

from llmc.docgen.graph_context import build_graph_context, load_graph_indices


class StubDatabase:
    def fetch_enrichment_by_span_hash(self, hash):
        return None

@pytest.fixture
def repo_root(tmp_path):
    (tmp_path / ".llmc").mkdir()
    return tmp_path

def test_load_graph_indices_invalid_json(repo_root):
    """Test that invalid JSON in graph file is handled gracefully."""
    graph_path = repo_root / ".llmc" / "rag_graph.json"
    with open(graph_path, "w") as f:
        f.write("{ invalid json")
    
    assert load_graph_indices(repo_root) is None

def test_load_graph_indices_not_a_dict(repo_root):
    """Test that valid JSON which is not a dict is handled gracefully."""
    graph_path = repo_root / ".llmc" / "rag_graph.json"
    with open(graph_path, "w") as f:
        f.write("[]")  # Valid JSON list, not dict
    
    assert load_graph_indices(repo_root) is None

def test_build_graph_context_entities_not_dict(repo_root):
    """Test that graph with 'entities' as list (not dict) crashes or handles."""
    # This exposes the potential bug in build_graph_context
    
    bad_graph = {
        "entities": [],  # Should be a dict
        "relations": []
    }
    
    db = StubDatabase()
    file_path = Path("some/file.py")
    
    # The current implementation does: entities.items()
    # If entities is a list, this should raise AttributeError
    
    try:
        build_graph_context(repo_root, file_path, db, cached_graph=bad_graph)
    except AttributeError:
        pytest.fail("CRASH: build_graph_context crashed when 'entities' is a list")
    except Exception as e:
        # Any other exception is also worth noting
        print(f"Caught expected exception: {e}")

def test_build_graph_context_relations_not_list(repo_root):
    """Test that graph with 'relations' as dict (not list) handles or crashes."""
    bad_graph = {
        "entities": {},
        "relations": {}  # Should be a list
    }
    
    db = StubDatabase()
    file_path = Path("some/file.py")
    
    # The implementation does: for relation in relations:
    # Iterating over a dict yields keys (strings). 
    # Then: relation.get("src") -> "string".get("src") -> AttributeError
    
    try:
        build_graph_context(repo_root, file_path, db, cached_graph=bad_graph)
    except AttributeError:
         pytest.fail("CRASH: build_graph_context crashed when 'relations' is a dict")
    except Exception as e:
        print(f"Caught expected exception: {e}")

def test_build_graph_context_entities_null(repo_root):
    """Test that graph with 'entities': null handles or crashes."""
    bad_graph = {
        "entities": None,
        "relations": []
    }
    
    db = StubDatabase()
    file_path = Path("some/file.py")
    
    # entities = graph_data.get("entities", {}) -> returns None if key exists and is null?
    # No, .get("key", default) only returns default if key is MISSING.
    # If key is present and value is None, it returns None.
    
    # So entities is None.
    # for ... in entities.items() -> AttributeError: 'NoneType' object has no attribute 'items'
    
    try:
        build_graph_context(repo_root, file_path, db, cached_graph=bad_graph)
    except AttributeError:
        pytest.fail("CRASH: build_graph_context crashed when 'entities' is None")
    except Exception as e:
        print(f"Caught expected exception: {e}")