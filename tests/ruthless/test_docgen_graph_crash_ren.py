
import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from llmc.docgen.graph_context import build_graph_context

class TestGraphCrashRen:
    """Ruthless testing for graph context stability."""

    @pytest.fixture
    def repo_root(self, tmp_path):
        (tmp_path / ".llmc").mkdir()
        return tmp_path

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        db.fetch_enrichment_by_span_hash.return_value = None
        return db

    def test_invalid_json_file(self, repo_root, mock_db):
        """Test with a corrupted JSON file."""
        graph_file = repo_root / ".llmc" / "rag_graph.json"
        graph_file.write_text("{ not valid json }")
        
        # Should not raise exception
        result = build_graph_context(repo_root, Path("test.py"), mock_db)
        assert "status: no_graph_data" in result

    def test_root_list_instead_of_dict(self, repo_root, mock_db):
        """Test with a list at root instead of dict."""
        graph_file = repo_root / ".llmc" / "rag_graph.json"
        graph_file.write_text("[]")
        
        result = build_graph_context(repo_root, Path("test.py"), mock_db)
        assert "status: no_graph_data" in result

    def test_entities_list_instead_of_dict(self, repo_root, mock_db):
        """Test with entities as list."""
        data = {"entities": [], "relations": []}
        graph_file = repo_root / ".llmc" / "rag_graph.json"
        graph_file.write_text(json.dumps(data))
        
        result = build_graph_context(repo_root, Path("test.py"), mock_db)
        assert "status: no_graph_data" in result

    def test_relations_dict_instead_of_list(self, repo_root, mock_db):
        """Test with relations as dict."""
        data = {
            "entities": {"e1": {"file_path": "test.py"}},
            "relations": {}
        }
        graph_file = repo_root / ".llmc" / "rag_graph.json"
        graph_file.write_text(json.dumps(data))
        
        result = build_graph_context(repo_root, Path("test.py"), mock_db)
        assert "status: no_graph_data" in result

    def test_malformed_relation_entry(self, repo_root, mock_db):
        """Test with a relation that isn't a dict."""
        data = {
            "entities": {"e1": {"file_path": "test.py"}},
            "relations": ["not a dict", {"src": "e1", "dst": "e2"}]
        }
        graph_file = repo_root / ".llmc" / "rag_graph.json"
        graph_file.write_text(json.dumps(data))
        
        # Should skip the string relation and process the valid one
        result = build_graph_context(repo_root, Path("test.py"), mock_db)
        assert "entity_count: 1" in result
        # If "dst": "e2" isn't in entities, it might not be included depending on logic.
        # The logic says: "Include relation if either endpoint is in our file"
        # e1 is in our file. So the valid relation should be included.
        assert "relation_count: 1" in result

    def test_db_missing_method(self, repo_root):
        """Test passing a DB without the required method."""
        bad_db = MagicMock()
        del bad_db.fetch_enrichment_by_span_hash
        
        with pytest.raises(TypeError, match="Expected database instance"):
            build_graph_context(repo_root, Path("test.py"), bad_db)
