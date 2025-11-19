import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from dataclasses import asdict

# We will need to import these after we create/modify them, but for now 
# we can mock or reference them to define the test structure.
# Ideally these imports would work once the code is written.
try:
    from tools.rag.schema import Entity, SchemaGraph
    from tools.rag.enrichment_db_helpers import load_enrichment_data, EnrichmentRecord
    from tools.rag_nav.tool_handlers import build_enriched_schema_graph
except ImportError:
    pass # Allow test collection to fail gracefully if modules don't exist yet

class TestGraphEnrichment:
    """Tests for Phase 2: Graph Enrichment logic."""

    def create_test_enrichment_db(self, repo_root: Path, records: list):
        """Helper to create a mock enrichment DB."""
        db_path = repo_root / ".llmc" / "rag" / "enrichment.db"
        if db_path.exists():
            db_path.unlink()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS enrichments (
                id INTEGER PRIMARY KEY,
                span_hash TEXT,
                file_path TEXT,
                start_line INTEGER,
                end_line INTEGER,
                summary TEXT,
                usage_guide TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        for r in records:
            conn.execute("""
                INSERT INTO enrichments (span_hash, file_path, start_line, end_line, summary, usage_guide)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (r.span_hash, r.file_path, r.start_line, r.end_line, r.summary, r.usage_guide))
            
        conn.commit()
        conn.close()
        return db_path

    def test_entity_has_metadata_field(self):
        """Test 3.1: Entity schema update."""
        from tools.rag.schema import Entity
        e = Entity(
            id="test", kind="func", path="t.py", file_path="t.py", 
            start_line=1, end_line=10, span_hash="abc",
            metadata={"key": "value"}
        )
        assert e.metadata == {"key": "value"}

    def test_load_enrichment_data_valid(self, tmp_path):
        """Test 1.2: Load from valid DB."""
        from tools.rag.enrichment_db_helpers import load_enrichment_data, EnrichmentRecord
        
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        
        record = EnrichmentRecord(
            span_hash="hash123", file_path="test.py", start_line=1, end_line=10,
            summary="A summary", usage_guide="Do this"
        )
        self.create_test_enrichment_db(repo_root, [record])
        
        data = load_enrichment_data(repo_root)
        assert "hash123" in data
        assert len(data["hash123"]) == 1
        assert data["hash123"][0].summary == "A summary"

    def test_load_enrichment_data_missing_db(self, tmp_path):
        """Test 1.1: Load from non-existent DB."""
        from tools.rag.enrichment_db_helpers import load_enrichment_data
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        
        data = load_enrichment_data(repo_root)
        assert data == {}

    def test_build_enriched_graph_integration(self, tmp_path):
        """Test 2.1: Happy Path Integration."""
        # 1. Setup Repo
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".llmc" / "rag").mkdir(parents=True, exist_ok=True)
        
        # 2. Mock base graph building
        # We'll patch the internal builder to return a known graph
        from tools.rag.schema import SchemaGraph, Entity
        from tools.rag_nav.tool_handlers import build_enriched_schema_graph
        
        base_entity = Entity(
            id="func_1", kind="function", path="src/main.py",
            file_path="src/main.py", start_line=10, end_line=20,
            span_hash="hash_func_1"
        )
        base_graph = SchemaGraph(
            repo=str(repo_root),
            entities=[base_entity],
            relations=[]
        )
        
        # 3. Setup Enrichment DB
        from tools.rag.enrichment_db_helpers import EnrichmentRecord
        record = EnrichmentRecord(
            span_hash="hash_func_1", file_path="src/main.py", 
            start_line=10, end_line=20,
            summary="Calculates complexity", usage_guide="Use with care"
        )
        self.create_test_enrichment_db(repo_root, [record])
        
        # 4. Run Enrichment
        # We patch the 'structural' builder to return our object
        with patch("tools.rag_nav.tool_handlers._build_base_structural_schema_graph", return_value=base_graph):
            # And we assume _save_schema_graph works or we can mock it to verify output
            with patch("tools.rag_nav.tool_handlers._save_schema_graph") as mock_save:
                result_graph = build_enriched_schema_graph(repo_root)
                
                # 5. Assertions
                assert len(result_graph.entities) == 1
                enriched_entity = result_graph.entities[0]
                assert enriched_entity.metadata["summary"] == "Calculates complexity"
                assert enriched_entity.metadata["usage_guide"] == "Use with care"
                
                # Verify save was called
                mock_save.assert_called_once()

    def test_build_enriched_graph_no_match(self, tmp_path):
        """Test 2.3: Partial Enrichment (No match for entity)."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        
        from tools.rag.schema import SchemaGraph, Entity
        from tools.rag_nav.tool_handlers import build_enriched_schema_graph
        
        base_entity = Entity(
            id="func_2", kind="function", path="src/main.py",
            file_path="src/main.py", start_line=30, end_line=40,
            span_hash="hash_func_2"
        )
        base_graph = SchemaGraph(repo=str(repo_root), entities=[base_entity], relations=[])
        
        # DB has record for DIFFERENT hash
        from tools.rag.enrichment_db_helpers import EnrichmentRecord
        record = EnrichmentRecord(
            span_hash="hash_func_1", file_path="src/main.py", 
            start_line=10, end_line=20, summary="Diff func"
        )
        self.create_test_enrichment_db(repo_root, [record])
        
        with patch("tools.rag_nav.tool_handlers._build_base_structural_schema_graph", return_value=base_graph):
            with patch("tools.rag_nav.tool_handlers._save_schema_graph"):
                result_graph = build_enriched_schema_graph(repo_root)
                assert result_graph.entities[0].metadata == {}