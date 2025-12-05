import json
from pathlib import Path

import pytest

from llmc.docgen.graph_context import build_graph_context


class MockDB:
    def fetch_enrichment_by_span_hash(self, span_hash):
        return None

def test_graph_invalid_root_structure(tmp_path):
    """Test that a non-dict root object is handled gracefully."""
    repo_root = tmp_path
    llmc_dir = repo_root / ".llmc"
    llmc_dir.mkdir()
    graph_path = llmc_dir / "rag_graph.json"
    
    # Write a list instead of dict
    graph_path.write_text("[]")
    
    context = build_graph_context(repo_root, Path("foo.py"), MockDB())
    assert "status: no_graph_data" in context

def test_graph_invalid_entities_type(tmp_path):
    """Test that non-dict 'entities' field is handled."""
    repo_root = tmp_path
    llmc_dir = repo_root / ".llmc"
    llmc_dir.mkdir()
    graph_path = llmc_dir / "rag_graph.json"
    
    # entities is a list
    graph_path.write_text(json.dumps({"entities": [], "relations": []}))
    
    context = build_graph_context(repo_root, Path("foo.py"), MockDB())
    assert "status: no_graph_data" in context

def test_graph_invalid_relations_type(tmp_path):
    """Test that non-list 'relations' field is handled."""
    repo_root = tmp_path
    llmc_dir = repo_root / ".llmc"
    llmc_dir.mkdir()
    graph_path = llmc_dir / "rag_graph.json"
    
    # relations is a dict
    graph_path.write_text(json.dumps({
        "entities": {
            "e1": {"file_path": "foo.py", "kind": "func", "name": "foo"}
        },
        "relations": {} # Should be list
    }))
    
    context = build_graph_context(repo_root, Path("foo.py"), MockDB())
    # Should fall back to no graph context because it returns early on validation failure
    assert "status: no_graph_data" in context

def test_graph_malformed_relation_item(tmp_path):
    """Test that individual malformed relations are skipped but process continues."""
    repo_root = tmp_path
    llmc_dir = repo_root / ".llmc"
    llmc_dir.mkdir()
    graph_path = llmc_dir / "rag_graph.json"
    
    graph_path.write_text(json.dumps({
        "entities": {
            "e1": {"file_path": "foo.py", "kind": "func", "name": "foo"}
        },
        "relations": [
            "not-a-dict", # Garbage
            {"src": "e1", "edge": "calls", "dst": "e2"} # Valid
        ]
    }))
    
    context = build_graph_context(repo_root, Path("foo.py"), MockDB())
    
    # Should NOT be "no_graph_data" because it survived partial corruption
    assert "status: no_graph_data" not in context
    assert "entity_count: 1" in context
    assert "relation_count: 1" in context # The valid one survived

def test_graph_db_duck_typing():
    """Test that passing a non-compliant DB raises TypeError."""
    with pytest.raises(TypeError, match="Expected database instance"):
        build_graph_context(Path("/tmp"), Path("foo.py"), object())