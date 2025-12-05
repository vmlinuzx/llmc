
import json
from pathlib import Path
from unittest.mock import MagicMock

from llmc.docgen.graph_context import build_graph_context


def test_graph_context_malformed_json(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".llmc").mkdir()
    graph_file = repo_root / ".llmc" / "rag_graph.json"
    
    # 1. Invalid JSON syntax
    graph_file.write_text("{ bad json")
    db = MagicMock()
    db.fetch_enrichment_by_span_hash.return_value = None
    
    ctx = build_graph_context(repo_root, Path("foo.py"), db)
    assert "status: no_graph_data" in ctx
    
    # 2. Valid JSON but not a dict (list)
    graph_file.write_text("[]")
    ctx = build_graph_context(repo_root, Path("foo.py"), db)
    assert "status: no_graph_data" in ctx

def test_graph_context_malformed_structure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".llmc").mkdir()
    graph_file = repo_root / ".llmc" / "rag_graph.json"
    
    db = MagicMock()
    
    # 3. 'entities' is not a dict
    data = {
        "entities": [], # Wrong type
        "relations": []
    }
    graph_file.write_text(json.dumps(data))
    ctx = build_graph_context(repo_root, Path("foo.py"), db)
    assert "status: no_graph_data" in ctx

    # 4. 'relations' is not a list
    data = {
        "entities": {},
        "relations": {} # Wrong type
    }
    graph_file.write_text(json.dumps(data))
    ctx = build_graph_context(repo_root, Path("foo.py"), db)
    assert "status: no_graph_data" in ctx

def test_graph_context_malformed_relations_items(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".llmc").mkdir()
    graph_file = repo_root / ".llmc" / "rag_graph.json"
    
    db = MagicMock()
    
    # 5. 'relations' contains non-dict items
    data = {
        "entities": {
            "e1": {"file_path": "foo.py", "kind": "func", "name": "foo"}
        },
        "relations": [
            "bad_relation", # Not a dict
            {"src": "e1", "dst": "e2", "edge": "calls"} # Valid
        ]
    }
    graph_file.write_text(json.dumps(data))
    
    # Should skip the bad one and process the good one (if e2 existed, but here e1 exists)
    ctx = build_graph_context(repo_root, Path("foo.py"), db)
    
    assert "entity_count: 1" in ctx
    # relation count depends on filtering. 
    # Valid relation has src=e1. So it should be included.
    # The bad relation should be skipped without crashing.
    assert "relation_count: 1" in ctx
