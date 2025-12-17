"""
Tests for tech docs graph edge creation.

Phase 4 of Domain RAG Tech Docs implementation.
Tests REFERENCES, REQUIRES, and WARNS_ABOUT edge creation.
"""

import pytest
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

# Import test subjects
from llmc.rag.tech_docs_graph import (
    EdgeWriteResult,
    ensure_edges_table,
    find_span_by_topic,
    write_tech_docs_edges,
    get_tech_docs_edges_stats,
)
from llmc.rag.schemas.tech_docs_enrichment import TechDocsEnrichment
from llmc.rag.graph import EdgeType


@pytest.fixture
def mock_db(tmp_path):
    """Create a mock database with spans for testing."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    
    # Create minimum required tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE
        );
        
        CREATE TABLE IF NOT EXISTS spans (
            id INTEGER PRIMARY KEY,
            file_id INTEGER,
            span_hash TEXT UNIQUE NOT NULL,
            symbol TEXT,
            kind TEXT,
            start_line INTEGER,
            end_line INTEGER,
            FOREIGN KEY (file_id) REFERENCES files(id)
        );
        
        CREATE TABLE IF NOT EXISTS enrichments (
            rowid INTEGER PRIMARY KEY,
            span_hash TEXT UNIQUE NOT NULL,
            payload TEXT
        );
    """)
    
    # Insert test data
    conn.executescript("""
        INSERT INTO files (id, path) VALUES (1, 'DOCS/installation.md');
        INSERT INTO files (id, path) VALUES (2, 'tools/rag/extractor.py');
        INSERT INTO files (id, path) VALUES (3, 'DOCS/oauth.md');
        
        INSERT INTO spans (file_id, span_hash, symbol, kind, start_line, end_line)
        VALUES 
            (1, 'hash_install', 'Installation', 'section', 1, 50),
            (2, 'hash_extractor', 'TechDocsExtractor', 'class', 10, 100),
            (3, 'hash_oauth', 'OAuth2', 'section', 1, 30);
    """)
    conn.commit()
    
    # Create mock Database object
    mock = MagicMock()
    mock.conn = conn
    mock.fts_available = False  # Property, not method
    
    yield mock
    
    conn.close()


@pytest.fixture
def sample_enrichment():
    """Create a sample TechDocsEnrichment for testing."""
    return TechDocsEnrichment(
        span_id="test_span_id",
        summary="A test document about installation procedures",
        key_concepts=["installation", "setup", "configuration"],
        prerequisites=["Python 3.10+", "TechDocsExtractor"],
        warnings=["Data loss possible", "Backup first"],
        related_topics=["OAuth2", "Installation"],
        audience="developer",
    )


class TestEnsureEdgesTable:
    """Tests for ensure_edges_table function."""
    
    def test_creates_table_if_not_exists(self, mock_db):
        """Should create tech_docs_edges table."""
        result = ensure_edges_table(mock_db)
        assert result is True
        
        # Verify table exists
        cursor = mock_db.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='tech_docs_edges'
        """)
        assert cursor.fetchone() is not None
    
    def test_idempotent(self, mock_db):
        """Should not fail if table already exists."""
        ensure_edges_table(mock_db)
        result = ensure_edges_table(mock_db)
        assert result is True


class TestFindSpanByTopic:
    """Tests for find_span_by_topic function."""
    
    def test_exact_symbol_match(self, mock_db):
        """Should find span by exact symbol match."""
        ensure_edges_table(mock_db)
        result = find_span_by_topic(mock_db, "TechDocsExtractor")
        assert result == "hash_extractor"
    
    def test_case_insensitive_match(self, mock_db):
        """Should match symbols case-insensitively."""
        ensure_edges_table(mock_db)
        result = find_span_by_topic(mock_db, "techdocsextractor")
        assert result == "hash_extractor"
    
    def test_partial_symbol_match(self, mock_db):
        """Should match partial symbol names."""
        ensure_edges_table(mock_db)
        result = find_span_by_topic(mock_db, "Extractor")
        assert result == "hash_extractor"
    
    def test_file_path_match(self, mock_db):
        """Should match file paths for doc references."""
        ensure_edges_table(mock_db)
        result = find_span_by_topic(mock_db, "installation.md")
        assert result == "hash_install"
    
    def test_no_match_returns_none(self, mock_db):
        """Should return None for unmatched topics."""
        ensure_edges_table(mock_db)
        result = find_span_by_topic(mock_db, "NonExistentTopic")
        assert result is None
    
    def test_empty_topic_returns_none(self, mock_db):
        """Should return None for empty topics."""
        ensure_edges_table(mock_db)
        result = find_span_by_topic(mock_db, "")
        assert result is None


class TestWriteTechDocsEdges:
    """Tests for write_tech_docs_edges function."""
    
    def test_creates_references_edges(self, mock_db, sample_enrichment):
        """Should create REFERENCES edges from related_topics."""
        ensure_edges_table(mock_db)
        
        result = write_tech_docs_edges(
            db=mock_db,
            span_hash="source_hash",
            enrichment=sample_enrichment,
        )
        
        assert isinstance(result, EdgeWriteResult)
        # related_topics has 2 items, both should create edges
        # (OAuth2 and Installation should match our test spans)
        assert result.edges_created >= 2
    
    def test_creates_requires_edges(self, mock_db, sample_enrichment):
        """Should create REQUIRES edges from prerequisites."""
        ensure_edges_table(mock_db)
        
        result = write_tech_docs_edges(
            db=mock_db,
            span_hash="source_hash",
            enrichment=sample_enrichment,
        )
        
        # Check that REQUIRES edges were created
        cursor = mock_db.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM tech_docs_edges 
            WHERE edge_type = 'REQUIRES' AND source_span_hash = 'source_hash'
        """)
        count = cursor.fetchone()[0]
        # prerequisites has 2 items
        assert count == 2
    
    def test_creates_warns_about_edges(self, mock_db, sample_enrichment):
        """Should create WARNS_ABOUT edges from warnings."""
        ensure_edges_table(mock_db)
        
        result = write_tech_docs_edges(
            db=mock_db,
            span_hash="source_hash",
            enrichment=sample_enrichment,
        )
        
        # Check that WARNS_ABOUT edges were created
        cursor = mock_db.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM tech_docs_edges 
            WHERE edge_type = 'WARNS_ABOUT' AND source_span_hash = 'source_hash'
        """)
        count = cursor.fetchone()[0]
        # warnings has 2 items
        assert count == 2
    
    def test_idempotent_no_duplicates(self, mock_db, sample_enrichment):
        """Should not create duplicate edges on re-enrichment."""
        ensure_edges_table(mock_db)
        
        # Write edges twice
        result1 = write_tech_docs_edges(
            db=mock_db,
            span_hash="source_hash",
            enrichment=sample_enrichment,
        )
        result2 = write_tech_docs_edges(
            db=mock_db,
            span_hash="source_hash",
            enrichment=sample_enrichment,
        )
        
        # First call should create edges
        assert result1.edges_created > 0
        # Second call should skip all (duplicates)
        assert result2.edges_created == 0
        assert result2.edges_skipped > 0
    
    def test_tracks_unresolved_edges(self, mock_db):
        """Should track edges where target wasn't found."""
        ensure_edges_table(mock_db)
        
        # Create enrichment with unmatchable topics
        enrichment = TechDocsEnrichment(
            span_id="test",
            summary="Test",
            related_topics=["CompletelyUnmatchableTopic12345"],
        )
        
        result = write_tech_docs_edges(
            db=mock_db,
            span_hash="source_hash",
            enrichment=enrichment,
        )
        
        assert result.edges_unresolved == 1


class TestGetTechDocsEdgesStats:
    """Tests for get_tech_docs_edges_stats function."""
    
    def test_empty_stats_when_no_table(self, mock_db):
        """Should return empty stats when table doesn't exist."""
        stats = get_tech_docs_edges_stats(mock_db)
        assert stats["total"] == 0
    
    def test_counts_edges_by_type(self, mock_db, sample_enrichment):
        """Should count edges grouped by type."""
        ensure_edges_table(mock_db)
        
        write_tech_docs_edges(
            db=mock_db,
            span_hash="source_hash",
            enrichment=sample_enrichment,
        )
        
        stats = get_tech_docs_edges_stats(mock_db)
        
        assert stats["total"] > 0
        assert "REFERENCES" in stats["by_type"] or "REQUIRES" in stats["by_type"]
    
    def test_tracks_resolved_vs_unresolved(self, mock_db, sample_enrichment):
        """Should track resolved vs unresolved edge counts."""
        ensure_edges_table(mock_db)
        
        write_tech_docs_edges(
            db=mock_db,
            span_hash="source_hash",
            enrichment=sample_enrichment,
        )
        
        stats = get_tech_docs_edges_stats(mock_db)
        
        # Should have some resolved (matching test spans) and some unresolved
        assert stats["resolved"] >= 0
        assert stats["unresolved"] >= 0
        assert stats["resolved"] + stats["unresolved"] == stats["total"]


class TestEdgeTypes:
    """Tests for edge type definitions."""
    
    def test_tech_docs_edge_types_defined(self):
        """Should have all required tech docs edge types in enum."""
        assert hasattr(EdgeType, "REFERENCES")
        assert hasattr(EdgeType, "REQUIRES")
        assert hasattr(EdgeType, "WARNS_ABOUT")
    
    def test_edge_type_values(self):
        """Edge types should have correct string values."""
        assert EdgeType.REFERENCES.value == "REFERENCES"
        assert EdgeType.REQUIRES.value == "REQUIRES"
        assert EdgeType.WARNS_ABOUT.value == "WARNS_ABOUT"
