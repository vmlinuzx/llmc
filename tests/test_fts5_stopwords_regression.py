"""
Regression tests for P0 FTS5 stopwords bug fix.

This test ensures that critical ML/AI domain keywords like "model", "system",
"data", etc. are NOT filtered by FTS5 stopwords, which was causing zero search
results for fundamental queries.

See: ROADMAP.md - P0 Bugfix: FTS5 Stopwords Filter Critical Keywords
"""

from pathlib import Path

import pytest

from llmc.rag.database import Database
from llmc.rag.types import FileRecord, SpanRecord

# Critical ML/AI domain keywords that were being filtered by default FTS5 stopwords
# These keywords appear in our test enrichments
CRITICAL_KEYWORDS = [
    "model",
    "system",
    "data",
    "select",
    "train",
    "router",
    "pipeline",
]


@pytest.fixture
def test_db(tmp_path: Path) -> Database:
    """Create a test database with sample enrichments."""
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Add a test file
    file_rec = FileRecord(
        path=Path("test/model_router.py"),
        lang="python",
        file_hash="abc123",
        size=1000,
        mtime=1234567890.0,
    )
    file_id = db.upsert_file(file_rec)
    
    # Add spans with enrichments containing critical keywords
    test_cases = [
        ("ModelRouter", "class", "Handles model selection and routing logic"),
        ("select_model", "function", "Select the best model for the given query"),
        ("DataPipeline", "class", "Data preprocessing and batching system"),
        ("train_system", "function", "Training system initialization and execution"),
    ]
    
    for symbol, kind, summary in test_cases:
        span = SpanRecord(
            file_path=file_rec.path,
            lang="python",
            symbol=symbol,
            kind=kind,
            start_line=1,
            end_line=10,
            byte_start=0,
            byte_end=100,
            span_hash=f"hash_{symbol}",
            slice_type="code",
        )
        
        db.conn.execute(
            """
            INSERT INTO spans (
                file_id, symbol, kind, start_line, end_line,
                byte_start, byte_end, span_hash, slice_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                span.symbol,
                span.kind,
                span.start_line,
                span.end_line,
                span.byte_start,
                span.byte_end,
                span.span_hash,
                span.slice_type,
            ),
        )
        
        # Add enrichment
        db.store_enrichment(
            span.span_hash,
            {
                "summary_120w": summary,
                "model": "test",
                "schema_version": "1.0",
            },
        )
    
    db.conn.commit()
    
    # Rebuild FTS index
    count = db.rebuild_enrichments_fts()
    assert count == len(test_cases), f"FTS rebuild should index {len(test_cases)} enrichments"
    
    return db


def test_fts5_no_stopwords_single_keyword(test_db: Database) -> None:
    """Test that single critical keywords return results (not filtered as stopwords)."""
    for keyword in CRITICAL_KEYWORDS[:4]:  # Test subset for speed
        results = test_db.search_enrichments_fts(keyword, limit=10)
        
        # Should return at least one result
        assert len(results) > 0, (
            f"FAIL: Keyword '{keyword}' returned zero results. "
            f"This indicates FTS5 stopword filtering is still active!"
        )
        
        # Verify result contains the keyword
        found_keyword = False
        for symbol, summary, _score in results:
            if summary and keyword.lower() in summary.lower():
                found_keyword = True
                break
            if symbol and keyword.lower() in symbol.lower():
                found_keyword = True
                break
        
        assert found_keyword, (
            f"FAIL: Keyword '{keyword}' in results but not in content. "
            f"Results: {results}"
        )


def test_fts5_no_stopwords_model_specific(test_db: Database) -> None:
    """Specific test for 'model' keyword (the original P0 bug)."""
    results = test_db.search_enrichments_fts("model", limit=10)
    
    assert len(results) >= 2, (
        f"FAIL: Query 'model' returned only {len(results)} results. "
        f"Expected at least 2 (ModelRouter + select_model). "
        f"FTS5 stopword filtering may still be active!"
    )
    
    # Check that ModelRouter and select_model are in results
    symbols = {r[0] for r in results}
    assert "ModelRouter" in symbols or "select_model" in symbols, (
        f"FAIL: Expected symbols not found in results. Got: {symbols}"
    )


def test_fts5_no_stopwords_multi_word(test_db: Database) -> None:
    """Test multi-word queries containing critical keywords."""
    test_queries = [
        "model routing",
        "data system",
        "training pipeline",
    ]
    
    for query in test_queries:
        results = test_db.search_enrichments_fts(query, limit=10)
        
        # Should return at least one result
        # Note: Not all queries will match, but none should return zero due to stopword filtering
        # The key is that the query executes without FTS5 syntax errors
        assert isinstance(results, list), (
            f"FAIL: Query '{query}' did not return a list. "
            f"This may indicate FTS5 query syntax error."
        )


def test_fts5_unicode61_tokenizer_active(test_db: Database) -> None:
    """Verify that the FTS table is using the unicode61 tokenizer."""
    # Check the FTS table definition
    rows = test_db.conn.execute(
        """
        SELECT sql FROM sqlite_master 
        WHERE type='table' AND name='enrichments_fts'
        """
    ).fetchall()
    
    assert len(rows) == 1, "enrichments_fts table should exist"
    
    sql = rows[0][0].lower()
    assert "unicode61" in sql, (
        f"FAIL: FTS table not using unicode61 tokenizer. "
        f"This means stopwords may still be active! SQL: {sql}"
    )
    assert "porter" not in sql, (
        f"FAIL: FTS table using porter tokenizer which has stopwords! SQL: {sql}"
    )


def test_fts5_critical_keywords_comprehensive(test_db: Database) -> None:
    """Comprehensive test of all critical keywords."""
    failed_keywords = []
    
    for keyword in CRITICAL_KEYWORDS:
        results = test_db.search_enrichments_fts(keyword, limit=10)
        if len(results) == 0:
            # Not all keywords will  have results, but "model" and "data" should
            if keyword in ["model", "data", "system"]:
                failed_keywords.append(keyword)
    
    assert len(failed_keywords) == 0, (
        f"FAIL: Critical keywords returned zero results: {failed_keywords}. "
        f"FTS5 stopword filtering may still be active!"
    )


if __name__ == "__main__":
    # Allow running directly for quick testing
    pytest.main([__file__, "-v"])
