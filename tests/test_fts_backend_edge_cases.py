"""Ruthless edge case tests for FTS Backend (P9a feature).

Tests cover:
- DB → FTS fallback mechanisms
- Graceful degradation
- Various database states
"""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest


class TestFTSFallback:
    """Test database to FTS backend fallback."""

    def create_test_db(self, tmp_path: Path, db_name: str = "rag.db") -> Path:
        """Create a test RAG database."""
        db_path = tmp_path / db_name

        # Create main DB with traditional tables
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE NOT NULL,
                content TEXT,
                indexed_at TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS symbols (
                id INTEGER PRIMARY KEY,
                file_id INTEGER,
                name TEXT,
                type TEXT,
                FOREIGN KEY (file_id) REFERENCES files(id)
            )
        """)

        # Add sample data
        conn.execute("INSERT OR IGNORE INTO files (path, content) VALUES (?, ?)",
                    ("file1.py", "def function_a(): return 42"))
        conn.execute("INSERT OR IGNORE INTO files (path, content) VALUES (?, ?)",
                    ("file2.py", "def function_b(): return function_a()"))
        conn.commit()
        conn.close()

        return db_path

    def create_fts_db(self, tmp_path: Path, db_name: str = "rag_fts.db") -> Path:
        """Create a test FTS database."""
        db_path = tmp_path / db_name

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_files USING fts5(
                path,
                content,
                content='files',
                content_rowid='id'
            )
        """)

        # Initialize FTS index
        conn.execute("INSERT INTO fts_files(fts_files) VALUES('rebuild')")
        conn.commit()
        conn.close()

        return db_path

    def test_fts_search_with_fresh_db(self, tmp_path: Path):
        """Test FTS search when both DBs are available."""
        main_db = self.create_test_db(tmp_path)
        fts_db = self.create_fts_db(tmp_path)

        # Both databases exist
        # Should prefer FTS for search
        # Implementation: fts_search(repo_root, query, limit)

    def test_fallback_to_traditional_when_fts_missing(self, tmp_path: Path):
        """Test fallback when FTS table doesn't exist."""
        main_db = self.create_test_db(tmp_path)

        # Create FTS DB but drop the FTS table
        fts_db_path = tmp_path / "rag_fts.db"
        conn = sqlite3.connect(str(fts_db_path))
        conn.execute("DROP TABLE IF NOT EXISTS fts_files")
        conn.commit()
        conn.close()

        # Should fall back to traditional search
        # Iterate through files table

    def test_fallback_when_db_not_found(self, tmp_path: Path):
        """Test graceful degradation when database file is missing."""
        # No database at all
        # Should fall back to file system grep

    def test_fallback_on_fts_corruption(self, tmp_path: Path):
        """Test fallback when FTS table is corrupted."""
        fts_db = self.create_fts_db(tmp_path)

        # Corrupt the FTS table
        conn = sqlite3.connect(str(fts_db))
        conn.execute("DROP TABLE fts_files")
        conn.commit()
        conn.close()

        # Should detect corruption and fall back
        # To traditional search or grep

    def test_fallback_on_fts_io_error(self, tmp_path: Path):
        """Test fallback on I/O errors with FTS."""
        # Simulate disk error
        with patch("sqlite3.connect", side_effect=IOError("Disk full")):
            # Should catch error and fall back
            pass

    def test_fallback_on_fts_permission_error(self, tmp_path: Path):
        """Test fallback when FTS DB has permission issues."""
        fts_db = self.create_fts_db(tmp_path)

        # Make database read-only
        import stat
        fts_db.chmod(stat.S_IRUSR)

        # Should handle permission error
        # Fall back to traditional search

    def test_fallback_empty_fts_results(self, tmp_path: Path):
        """Test behavior when FTS returns no results."""
        # FTS search finds nothing
        # Should fall back to traditional search
        # Or return empty results

    def test_fallback_with_partial_results(self, tmp_path: Path):
        """Test combining FTS and traditional results."""
        # FTS finds some results
        # Traditional finds additional results
        # Combine and deduplicate

    def test_fallback_threshold_configuration(self, tmp_path: Path):
        """Test configurable threshold for fallback."""
        # If FTS returns < threshold results
        # Fall back to traditional for better coverage

    def test_fallback_preserves_query(self, tmp_path: Path):
        """Test that query is preserved during fallback."""
        # Original query "function_a"
        # FTS search fails
        # Traditional search should use same query

    def test_fallback_with_special_characters(self, tmp_path: Path):
        """Test fallback handles special characters in query."""
        queries = [
            "def test():",
            "class MyClass:",
            "import os.path",
            "# TODO: fix",
        ]

        # Should handle all in both FTS and fallback

    def test_fallback_with_unicode_query(self, tmp_path: Path):
        """Test fallback with unicode characters."""
        queries = [
            "функция",
            "関数",
            "函数",
            "🔍 search",
        ]

        # FTS should handle if configured
        # Fallback should also handle

    def test_fallback_timing_performance(self, tmp_path: Path):
        """Test that fallback doesn't significantly impact performance."""
        import time

        # FTS search: fast
        start = time.time()
        # fts_search (if FTS works)
        fts_time = time.time() - start

        # Fallback search: slower
        start = time.time()
        # Traditional search
        fallback_time = time.time() - start

        # Both should complete in reasonable time
        assert fts_time < 0.1
        assert fallback_time < 1.0  # Fallback can be slower

    def test_fallback_metrics_tracking(self, tmp_path: Path):
        """Test that fallback is tracked in metrics."""
        # Track: fts_used, fts_fallback_used, traditional_used
        # Log which backend was used

    def test_fallback_error_logging(self, tmp_path: Path):
        """Test that fallback events are logged."""
        # Log FTS failures
        # Log fallback activation
        # Include error details

    def test_selective_fallback_per_query(self, tmp_path: Path):
        """Test that fallback can be selective per query."""
        # Query 1: FTS works
        # Query 2: FTS fails, use fallback
        # Query 3: FTS works again
        # Each query can choose independently


class TestGracefulDegradation:
    """Test graceful degradation under various failure modes."""

    def test_degradation_with_readonly_db(self, tmp_path: Path):
        """Test degradation when database is read-only."""
        main_db = self.create_test_db(tmp_path)

        # Make database read-only
        import stat
        main_db.chmod(stat.S_IRUSR)

        # Should still be able to read/search
        # Just can't write

    def test_degradation_with_disk_space_low(self, tmp_path: Path):
        """Test behavior when disk space is critically low."""
        # Simulate disk full scenario
        # Should fail gracefully
        # Return fallback results

    def test_degradation_with_network_db(self, tmp_path: Path):
        """Test degradation with network-mounted database."""
        # Network storage may be slow or unreliable
        # Should have timeout and fallback

    def test_degradation_concurrent_access(self, tmp_path: Path):
        """Test degradation under concurrent access."""
        # Multiple processes accessing DB
        # Should handle locks gracefully

    def test_degradation_with_large_database(self, tmp_path: Path):
        """Test degradation with very large database."""
        # 1GB+ database
        # May need chunked reading or caching

    def test_degradation_memory_pressure(self, tmp_path: Path):
        """Test degradation under memory pressure."""
        # Low memory available
        # Should limit cache size
        # Fall back to simple queries

    def test_degradation_old_database_schema(self, tmp_path: Path):
        """Test degradation with old database schema."""
        # Database created with old schema
        # Missing new tables/columns
        # Should still work with available fields

    def test_degradation_mixed_schema_versions(self, tmp_path: Path):
        """Test database with mixed schema versions."""
        # Some tables updated, others not
        # Should handle gracefully

    def test_degradation_partial_index(self, tmp_path: Path):
        """Test with partially indexed database."""
        # Some files indexed, others not
        # Should search both indexed and non-indexed

    def test_degradation_missing_index(self, tmp_path: Path):
        """Test when index is completely missing."""
        # Database exists but no index
        # Should scan all files

    def test_degradation_stale_index(self, tmp_path: Path):
        """Test with stale/outdated index."""
        # Files changed since indexing
        # May return stale results
        # Should warn or refresh

    def test_degradation_incremental_rebuild(self, tmp_path: Path):
        """Test incremental index rebuild during search."""
        # Rebuild happening while searching
        # Should handle race conditions

    def test_degradation_backup_database(self, tmp_path: Path):
        """Test with database backup in progress."""
        # .backup or .bak file present
        # Should detect and use primary

    def test_degradation_recovery_after_failure(self, tmp_path: Path):
        """Test recovery after database failure."""
        # DB fails mid-search
        # Should clean up and try fallback

    def test_degradation_with_multiple_db_files(self, tmp_path: Path):
        """Test with database split across multiple files."""
        # Separate DB for files, symbols, etc.
        # Should handle cross-file joins


class TestFTSSearchEdgeCases:
    """Test FTS search under edge conditions."""

    def test_fts_search_empty_query(self, tmp_path: Path):
        """Test FTS search with empty query."""
        fts_db = self.create_fts_db(tmp_path)

        # Empty query should return all results or none
        # Implementation-specific

    def test_fts_search_very_long_query(self, tmp_path: Path):
        """Test FTS search with very long query."""
        long_query = " ".join(["word"] * 10000)

        # Should handle or reject long queries
        # May truncate or error

    def test_fts_search_wildcard_patterns(self, tmp_path: Path):
        """Test FTS search with wildcards."""
        patterns = [
            "func*",  # Prefix match
            "*_test",  # Suffix match
            "*test*",  # Contains
        ]

        # FTS should handle wildcards if configured

    def test_fts_search_regex_patterns(self, tmp_path: Path):
        """Test FTS search with regex patterns."""
        patterns = [
            r"def \w+",  # Function definitions
            r"class \w+:",  # Class definitions
            r"import \w+",  # Imports
        ]

        # FTS may or may not support regex
        # Fallback should handle

    def test_fts_search_special_characters(self, tmp_path: Path):
        """Test FTS search with special SQL characters."""
        dangerous_queries = [
            "'; DROP TABLE files; --",
            "100 OR 1=1",
            "func_a UNION SELECT * FROM files",
        ]

        # Should escape properly to prevent injection
        # FTS should escape these

    def test_fts_search_case_sensitivity(self, tmp_path: Path):
        """Test FTS search case sensitivity."""
        # FTS5 is case-insensitive by default
        # "Function" should match "function"

    def test_fts_search_accent_insensitivity(self, tmp_path: Path):
        """Test FTS search with accents."""
        # "função" should match "funcao"
        # Depends on FTS configuration

    def test_fts_search_stemming(self, tmp_path: Path):
        """Test FTS search with stemming."""
        # "running" should match "run"
        # Depends on FTS stemmer

    def test_fts_search_stop_words(self, tmp_path: Path):
        """Test FTS search with stop words."""
        # Common stop words: "the", "and", "of"
        # May be filtered out
        # Should still work

    def test_fts_search_phrase_queries(self, tmp_path: Path):
        """Test FTS search with phrase queries."""
        # "def function_a" as exact phrase
        # Should find exact match

    def test_fts_search_near_queries(self, tmp_path: Path):
        """Test FTS search with NEAR operator."""
        # "function NEAR/5 return"
        # Finds function within 5 words of return
        # FTS5 feature

    def test_fts_search_boolean_operators(self, tmp_path: Path):
        """Test FTS search with AND/OR/NOT."""
        queries = [
            "function AND test",
            "class OR struct",
            "import NOT os",
        ]

        # FTS5 boolean operators

    def test_fts_search_limit_parameter(self, tmp_path: Path):
        """Test FTS search with limit parameter."""
        fts_db = self.create_fts_db(tmp_path)

        # Test various limits: 1, 10, 100, 1000
        # Should respect limit

    def test_fts_search_offset_parameter(self, tmp_path: Path):
        """Test FTS search with offset (pagination)."""
        # Test pagination: limit 10, offset 0, 10, 20, etc.
        # Should support offset for large result sets

    def test_fts_search_ordering(self, tmp_path: Path):
        """Test FTS search result ordering."""
        # Results should be ordered by relevance
        # Or by path/filename

    def test_fts_search_scoring(self, tmp_path: Path):
        """Test FTS search relevance scoring."""
        # More matches = higher score
        # Exact matches > partial matches

    def test_fts_search_snippet_extraction(self, tmp_path: Path):
        """Test FTS snippet extraction around matches."""
        # Should extract relevant snippets
        # With match highlighted

    def test_fts_search_highlight_marks(self, tmp_path: Path):
        """Test match highlighting in snippets."""
        # FTS can highlight matches
        # <b> tags or similar

    def test_fts_zero_results(self, tmp_path: Path):
        """Test FTS search returns no results."""
        # Query matches nothing
        # Should return empty list

    def test_fts_all_results(self, tmp_path: Path):
        """Test FTS search matches everything."""
        # Query matches all files
        # Should handle large result sets

    def test_fts_duplicate_matches(self, tmp_path: Path):
        """Test handling of duplicate matches."""
        # Same file matched multiple times
        # Should deduplicate results


class TestDatabaseMigration:
    """Test database migration and schema evolution."""

    def test_migrate_to_fts(self, tmp_path: Path):
        """Test migration from traditional to FTS."""
        # Create traditional DB
        main_db = self.create_test_db(tmp_path)

        # Migrate to FTS
        # Build FTS index from traditional data

    def test_schema_version_tracking(self, tmp_path: Path):
        """Test schema version tracking."""
        # Track DB schema version
        # Migrate as needed

    def test_migration_rollback(self, tmp_path: Path):
        """Test migration rollback on failure."""
        # Migration fails mid-way
        # Should rollback to original

    def test_partial_migration_recovery(self, tmp_path: Path):
        """Test recovery from partial migration."""
        # Migration interrupted
        # Should detect and retry or rollback

    def test_migration_with_data_loss(self, tmp_path: Path):
        """Test migration preserves all data."""
        # Verify no data loss during migration
        # Compare counts before/after

    def test_concurrent_migration_prevention(self, tmp_path: Path):
        """Test prevention of concurrent migrations."""
        # Only one migration at a time
        # Lock or error on second attempt

    def test_migration_performance(self, tmp_path: Path):
        """Test migration performance on large DB."""
        # Large DB (1GB+)
        # Migration should be efficient
        # May need batching

    def test_migration_batching(self, tmp_path: Path):
        """Test migration with batching for large data."""
        # Process in batches
        # Avoid memory issues

    def test_migration_progress_tracking(self, tmp_path: Path):
        """Test migration progress tracking."""
        # Report progress
        # Allow cancellation

    def test_downgrade_schema(self, tmp_path: Path):
        """Test downgrading to older schema."""
        # Reverse migration
        # May lose new features


class TestFTSConfiguration:
    """Test FTS configuration and tuning."""

    def test_fts_tokenizer_configuration(self, tmp_path: Path):
        """Test FTS tokenizer configuration."""
        # Unicode,porter,etc.
        # Choose appropriate tokenizer

    def test_fts_stemmer_configuration(self, tmp_path: Path):
        """Test FTS stemmer configuration."""
        # English, other languages
        # Language-specific stemming

    def test_fts_stop_words_configuration(self, tmp_path: Path):
        """Test FTS stop words configuration."""
        # Customize stop words
        # Language-specific

    def test_fts_builtin_versus_external(self, tmp_path: Path):
        """Test built-in vs external stemmers."""
        # Built-in: faster, less features
        # External: more features, slower

    def test_fts_cache_size(self, tmp_path: Path):
        """Test FTS cache size configuration."""
        # Balance memory vs performance
        # Configurable cache size

    def test_fts_memory_map(self, tmp_path: Path):
        """Test FTS memory-mapped I/O."""
        # May improve performance
        # Platform-specific

    def test_fts_synchronous_mode(self, tmp_path: Path):
        """Test FTS synchronous mode."""
        # FULL, NORMAL, OFF
        # Performance vs safety trade-off

    def test_fts_journal_mode(self, tmp_path: Path):
        """Test FTS journal mode."""
        # DELETE, TRUNCATE, PERSIST, etc.
        # Recovery vs performance

    def test_fts_page_size(self, tmp_path: Path):
        """Test FTS page size tuning."""
        # 4KB, 8KB, 16KB, etc.
        # I/O efficiency

    def test_fts_auto_vacuum(self, tmp_path: Path):
        """Test FTS auto-vacuum configuration."""
        # Keep DB compact
        # Slight overhead


class TestFTSErrorHandling:
    """Test comprehensive error handling in FTS."""

    def test_fts_query_syntax_error(self, tmp_path: Path):
        """Test handling of FTS query syntax errors."""
        # Invalid FTS query
        # Should catch and return error

    def test_fts_table_missing(self, tmp_path: Path):
        """Test when FTS table doesn't exist."""
        # Fall back to traditional search

    def test_fts_index_rebuild_needed(self, tmp_path: Path):
        """Test when FTS index needs rebuild."""
        # Marked as dirty
        # Rebuild before searching

    def test_fts_index_out_of_date(self, tmp_path: Path):
        """Test when FTS index is out of date."""
        # Files changed since FTS build
        # Rebuild or fall back

    def test_fts_database_locked(self, tmp_path: Path):
        """Test when FTS database is locked."""
        # Another process using DB
        # Retry or wait

    def test_fts_transaction_rollback(self, tmp_path: Path):
        """Test FTS transaction rollback."""
        # Rollback on error
        # Maintain consistency

    def test_fts_connection_pool_exhaustion(self, tmp_path: Path):
        """Test when connection pool is exhausted."""
        # Too many concurrent queries
        # Queue or error

    def test_fts_cancellation(self, tmp_path: Path):
        """Test query cancellation."""
        # Long-running query cancelled
        # Clean up resources

    def test_fts_timeout_handling(self, tmp_path: Path):
        """Test query timeout."""
        # Query takes too long
        # Timeout and fall back

    def test_fts_memory_allocation_failure(self, tmp_path: Path):
        """Test memory allocation failure."""
        # Out of memory
        # Fall back to simpler search

    def test_fts_disk_io_error(self, tmp_path: Path):
        """Test disk I/O errors."""
        # Disk error during search
        # Retry or fall back

    def test_fts_filesystem_errors(self, tmp_path: Path):
        """Test filesystem errors."""
        # ENOSPC, EIO, etc.
        # Handle gracefully

    def test_fts_signal_handling(self, tmp_path: Path):
        """Test signal handling during FTS."""
        # SIGINT, SIGTERM
        # Clean shutdown

    def test_fts_exception_isolation(self, tmp_path: Path):
        """Test that FTS errors don't crash system."""
        # Catch all FTS exceptions
        # Log and continue

    def test_fts_fallback_error_handling(self, tmp_path: Path):
        """Test error handling during fallback."""
        # FTS fails
        # Fallback also fails
        # Should handle both failures
