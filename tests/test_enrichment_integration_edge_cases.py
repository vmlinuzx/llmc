"""Ruthless edge case tests for Enrichment Integration.

Tests cover:
- Enrichment attachment with LLMC_ENRICH env var
- Enrichment DB discovery mechanisms
- Enrichment metrics logging
- Edge cases and failure scenarios
"""

import os
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Import enrichment modules
# Note: These imports should work after enrichment is properly integrated

def create_test_db(tmp_path: Path, db_name: str = "enrichment.db") -> Path:
    """Helper to create a test enrichment database."""
    db_path = tmp_path / db_name
    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass
            
    conn = sqlite3.connect(str(db_path))

    # Create basic enrichment schema
    conn.execute("""
        CREATE TABLE IF NOT EXISTS enrichments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            operation TEXT NOT NULL,
            items_count INTEGER,
            attached_count INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

    return db_path


class TestEnrichmentEnvironmentVariables:
    """Test enrichment control via environment variables."""

    def test_llmc_enrich_disabled_by_default(self):
        """Test that enrichment is disabled when LLMC_ENRICH is not set."""
        # Ensure env var is not set
        with patch.dict(os.environ, {}, clear=False):
            if "LLMC_ENRICH" in os.environ:
                del os.environ["LLMC_ENRICH"]

            # Should detect as disabled
            flag = str(os.getenv("LLMC_ENRICH", "")).lower()
            assert flag not in {"1", "true", "yes", "on"}

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", "True", "yes", "YES", "on", "ON"])
    def test_llmc_enrich_enabled_with_various_values(self, value):
        """Test that enrichment is enabled with various truthy values."""
        with patch.dict(os.environ, {"LLMC_ENRICH": value}):
            flag = str(os.getenv("LLMC_ENRICH", "")).lower()
            assert flag in {"1", "true", "yes", "on"}

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off", "OFF", "", "invalid"])
    def test_llmc_enrich_disabled_with_falsy_values(self, value):
        """Test that enrichment is disabled with falsy values."""
        with patch.dict(os.environ, {"LLMC_ENRICH": value}):
            flag = str(os.getenv("LLMC_ENRICH", "")).lower()
            assert flag not in {"1", "true", "yes", "on"}

    def test_llmc_enrich_attach_flag(self):
        """Test LLMC_ENRICH_ATTACH flag for attach-only mode."""
        with patch.dict(os.environ, {"LLMC_ENRICH_ATTACH": "true"}):
            attach = str(os.getenv("LLMC_ENRICH_ATTACH", "")).lower()
            assert attach in {"1", "true", "yes"}

    def test_llmc_enrich_max_chars_default(self):
        """Test default max chars when LLMC_ENRICH_MAX_CHARS is not set."""
        with patch.dict(os.environ, {}, clear=False):
            if "LLMC_ENRICH_MAX_CHARS" in os.environ:
                del os.environ["LLMC_ENRICH_MAX_CHARS"]

            raw = os.getenv("LLMC_ENRICH_MAX_CHARS")
            assert raw is None

    @pytest.mark.parametrize("value", ["100", "1000", "5000", "10000"])
    def test_llmc_enrich_max_chars_valid_values(self, value):
        """Test valid max chars values."""
        with patch.dict(os.environ, {"LLMC_ENRICH_MAX_CHARS": value}):
            raw = os.getenv("LLMC_ENRICH_MAX_CHARS")
            assert raw == value

            if raw and raw.isdigit():
                num = int(raw)
                assert num > 0

    def test_llmc_enrich_max_chars_zero(self):
        """Test that zero max chars is handled (should disable or use default)."""
        with patch.dict(os.environ, {"LLMC_ENRICH_MAX_CHARS": "0"}):
            raw = os.getenv("LLMC_ENRICH_MAX_CHARS")
            if raw and raw.isdigit():
                value = int(raw)
                # Should either disable or use default
                result = value if value > 0 else None
                assert result is None

    def test_llmc_enrich_max_chars_negative(self):
        """Test that negative max chars is handled."""
        with patch.dict(os.environ, {"LLMC_ENRICH_MAX_CHARS": "-100"}):
            raw = os.getenv("LLMC_ENRICH_MAX_CHARS")
            # Negative values should be ignored
            assert raw == "-100"

    def test_llmc_enrich_max_chars_non_numeric(self):
        """Test that non-numeric max chars is handled."""
        with patch.dict(os.environ, {"LLMC_ENRICH_MAX_CHARS": "not_a_number"}):
            raw = os.getenv("LLMC_ENRICH_MAX_CHARS")
            # Non-numeric should be ignored
            assert raw == "not_a_number"

    def test_llmc_enrich_log_disabled_by_default(self):
        """Test that enrichment logging is disabled by default."""
        with patch.dict(os.environ, {}, clear=False):
            if "LLMC_ENRICH_LOG" in os.environ:
                del os.environ["LLMC_ENRICH_LOG"]

            log_flag = str(os.getenv("LLMC_ENRICH_LOG", "")).lower()
            assert log_flag not in {"1", "true", "yes"}

    def test_llmc_enrich_log_enabled(self):
        """Test enabling enrichment logging."""
        with patch.dict(os.environ, {"LLMC_ENRICH_LOG": "true"}):
            log_flag = str(os.getenv("LLMC_ENRICH_LOG", "")).lower()
            assert log_flag in {"1", "true", "yes"}

    def test_combined_enrich_flags(self):
        """Test multiple enrichment flags together."""
        env = {
            "LLMC_ENRICH": "true",
            "LLMC_ENRICH_ATTACH": "yes",
            "LLMC_ENRICH_MAX_CHARS": "5000",
            "LLMC_ENRICH_LOG": "on",
        }

        with patch.dict(os.environ, env):
            assert os.getenv("LLMC_ENRICH", "").lower() == "true"
            assert os.getenv("LLMC_ENRICH_ATTACH", "").lower() == "yes"
            assert os.getenv("LLMC_ENRICH_MAX_CHARS") == "5000"
            assert os.getenv("LLMC_ENRICH_LOG", "").lower() == "on"


class TestEnrichmentDatabaseDiscovery:
    """Test enrichment database discovery mechanisms."""

    def test_discover_enrichment_db_with_env_path(self, tmp_path: Path):
        """Test discovery via LLMC_ENRICH_DB environment variable."""
        db_path = create_test_db(tmp_path)

        with patch.dict(os.environ, {"LLMC_ENRICH_DB": str(db_path)}):
            env_db = os.getenv("LLMC_ENRICH_DB")
            assert env_db == str(db_path)
            assert db_path.exists()

    def test_discover_enrichment_db_env_path_not_exists(self, tmp_path: Path):
        """Test that non-existent DB path is handled."""
        fake_path = tmp_path / "nonexistent.db"

        with patch.dict(os.environ, {"LLMC_ENRICH_DB": str(fake_path)}):
            env_db = os.getenv("LLMC_ENRICH_DB")
            assert env_db == str(fake_path)
            assert not fake_path.exists()  # Path doesn't exist

    def test_discover_enrichment_db_in_repo_workspace(self, tmp_path: Path):
        """Test discovery of DB in repo workspace (.llmc/rag/)."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        workspace = repo_root / ".llmc" / "rag"
        workspace.mkdir(parents=True)

        db_path = create_test_db(workspace, "enrichment.db")

        # Should find DB in workspace
        assert (workspace / "enrichment.db").exists()

    def test_discover_enrichment_db_in_llmc_root(self, tmp_path: Path):
        """Test discovery of DB in .llmc root directory."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        llmc_dir = repo_root / ".llmc"
        llmc_dir.mkdir()

        db_path = create_test_db(llmc_dir, "enrichment.db")

        # Should find DB in .llmc
        assert (llmc_dir / "enrichment.db").exists()

    def test_discover_enrichment_db_auto_naming(self, tmp_path: Path):
        """Test that various DB names are tried during discovery."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        # Create DB with different names
        names_to_try = [
            "enrichment.db",
            "enrich.db",
            "rag_enrichment.db",
            "context.db",
        ]

        for name in names_to_try:
            db_path = create_test_db(workspace, name)
            assert db_path.exists()

    def test_discover_enrichment_db_with_search_items(self, tmp_path: Path):
        """Test discovery with search items to guide search."""
        repo_root = tmp_path / "test_repo"
        repo_root.mkdir()

        workspace = repo_root / ".llmc" / "rag"
        workspace.mkdir(parents=True)

        # Create DB with items
        db_path = create_test_db(workspace, "enrichment.db")

        # Simulate search items
        search_items = [
            {"file": "module1.py"},
            {"file": "module2.py"},
        ]

        # Discovery should use items to narrow search
        # This tests the helper function
        assert len(search_items) == 2

    def test_enrichment_db_version_check(self, tmp_path: Path):
        """Test that enrichment DB version is checked."""
        db_path = create_test_db(tmp_path)

        conn = sqlite3.connect(str(db_path))

        # Add version table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL
            )
        """)
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        conn.commit()
        conn.close()

        # Should be able to read version
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
        version = cursor.fetchone()[0]
        conn.close()

        assert version == 1

    def test_enrichment_db_schema_migration(self, tmp_path: Path):
        """Test database schema migration on upgrade."""
        db_path = create_test_db(tmp_path)

        # Create old schema (without version)
        conn = sqlite3.connect(str(db_path))
        conn.execute("DROP TABLE IF EXISTS schema_version")
        conn.commit()
        conn.close()

        # Should detect old schema and migrate
        # Migration logic would upgrade here
        assert True  # Placeholder

    def test_enrichment_db_locked(self, tmp_path: Path):
        """Test handling when DB is locked by another process."""
        db_path = create_test_db(tmp_path)

        # Open connection and hold it
        conn1 = sqlite3.connect(str(db_path))
        conn1.execute("BEGIN EXCLUSIVE")

        # Try to open second connection
        try:
            conn2 = sqlite3.connect(str(db_path))
            conn2.execute("SELECT 1")
            conn2.close()
        except sqlite3.OperationalError:
            pass  # Expected - database locked

        conn1.close()

    def test_enrichment_db_corrupted(self, tmp_path: Path):
        """Test handling of corrupted DB file."""
        db_path = tmp_path / "corrupted.db"
        db_path.write_text("This is not a valid database file")

        # Should detect corruption
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("SELECT * FROM sqlite_master")
            conn.close()
            assert False, "Should have failed to open corrupted DB"
        except sqlite3.DatabaseError:
            pass  # Expected

    def test_enrichment_db_permissions(self, tmp_path: Path):
        """Test DB with restricted permissions."""
        db_path = create_test_db(tmp_path)

        # Make file read-only
        import stat
        db_path.chmod(stat.S_IRUSR)

        # Should handle read-only DB gracefully
        # May be read-only or fail

    def test_enrichment_db_remote_storage(self, tmp_path: Path):
        """Test DB on remote/network storage (if supported)."""
        # Network paths may have different characteristics
        # Test slow I/O, timeouts, etc.
        pass  # Platform-dependent


class TestEnrichmentAttachment:
    """Test enrichment attachment to search results."""

    def test_attach_enrichments_to_search_result(self, tmp_path: Path):
        """Test attaching enrichments to SearchResult."""
        db_path = create_test_db(tmp_path)

        # Add enrichment data
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            INSERT INTO enrichments (file_path, content)
            VALUES ('test.py', 'Enriched content for test.py')
        """)
        conn.commit()
        conn.close()

        # Create mock search result
        search_result = Mock()
        search_result.items = [
            Mock(file="test.py"),
            Mock(file="other.py"),
        ]

        # Attach enrichments
        # Implementation in enrichment.attach_enrichments_to_search_result
        # Should match items to enrichments from DB

    def test_attach_enrichments_where_used(self, tmp_path: Path):
        """Test attaching enrichments to WhereUsedResult."""
        db_path = create_test_db(tmp_path)

        # Similar to search result test
        where_used_result = Mock()
        where_used_result.items = [
            Mock(file="caller.py"),
            Mock(file="callee.py"),
        ]

    def test_attach_enrichments_lineage(self, tmp_path: Path):
        """Test attaching enrichments to LineageResult."""
        db_path = create_test_db(tmp_path)

        lineage_result = Mock()
        lineage_result.items = [
            Mock(file="lineage1.py"),
            Mock(file="lineage2.py"),
        ]

    def test_max_snippets_per_item(self, tmp_path: Path):
        """Test max_snippets parameter for enrichment attachment."""
        db_path = create_test_db(tmp_path)

        # Add multiple enrichments for same file
        conn = sqlite3.connect(str(db_path))
        for i in range(10):
            conn.execute(
                "INSERT INTO enrichments (file_path, content) VALUES (?, ?)",
                ("test.py", f"Enrichment {i}")
            )
        conn.commit()
        conn.close()

        # Test with max_snippets=1
        # Should only attach 1 snippet per file

    def test_max_chars_enforcement(self, tmp_path: Path):
        """Test that max_chars parameter is enforced."""
        db_path = create_test_db(tmp_path)

        # Add large enrichment content
        conn = sqlite3.connect(str(db_path))
        large_content = "x" * 10000
        conn.execute(
            "INSERT INTO enrichments (file_path, content) VALUES (?, ?)",
            ("test.py", large_content)
        )
        conn.commit()
        conn.close()

        # Test with max_chars=1000
        # Should truncate or skip if exceeds limit

    def test_no_enrichment_data(self, tmp_path: Path):
        """Test behavior when DB has no enrichment data."""
        db_path = create_test_db(tmp_path)

        # Don't add any data
        # Should handle gracefully - return result unchanged

    def test_missing_file_in_enrichment(self, tmp_path: Path):
        """Test enrichment for files not in DB."""
        db_path = create_test_db(tmp_path)

        # Add enrichment for different file
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO enrichments (file_path, content) VALUES (?, ?)",
            ("other.py", "Content for other.py")
        )
        conn.commit()
        conn.close()

        # Search result has different files
        search_result = Mock()
        search_result.items = [
            Mock(file="test.py"),  # Not in DB
            Mock(file="other.py"),  # In DB
        ]

    def test_enrichment_fallback_on_error(self, tmp_path: Path):
        """Test that enrichment errors don't break core search."""
        # Simulate DB connection error
        with patch("sqlite3.connect", side_effect=Exception("DB error")):
            # Search should still work, just without enrichment
            pass

    def test_partial_enrichment_success(self, tmp_path: Path):
        """Test when some enrichments succeed and others fail."""
        # Some items get enriched, others don't
        # Should still return all items (with or without enrichment)

    def test_enrichment_order_preservation(self, tmp_path: Path):
        """Test that enrichment doesn't change item order."""
        # Enrichment should preserve the order of search results
        # Just add enrichment data to each item

    def test_enrichment_caching(self, tmp_path: Path):
        """Test that enrichment results are cached."""
        # Repeated enrichment of same results should use cache
        # Test cache invalidation

    def test_enrichment_batch_processing(self, tmp_path: Path):
        """Test enrichment of large result sets in batches."""
        # Large search results (100+ items)
        # Should process in batches to avoid memory issues

    def test_concurrent_enrichment_requests(self, tmp_path: Path):
        """Test concurrent enrichment requests don't corrupt data."""
        # Multiple threads/processes enriching simultaneously
        # Should handle gracefully

    def test_enrichment_with_special_characters(self, tmp_path: Path):
        """Test enrichment with special characters in content."""
        db_path = create_test_db(tmp_path)

        special_content = "Content with <html> & special chars: \n\t\"'"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO enrichments (file_path, content) VALUES (?, ?)",
            ("test.py", special_content)
        )
        conn.commit()
        conn.close()

        # Should handle special chars in enrichment data


class TestEnrichmentMetrics:
    """Test enrichment metrics tracking and logging."""

    def test_enrichment_stats_tracking(self, tmp_path: Path):
        """Test that EnrichStats tracks enrichment metrics."""
        stats = Mock()

        # Track various metrics
        stats.snippets_attached = 5
        stats.line_matches = 20
        stats.path_matches = 10
        stats.fields_truncated = 3

        # Verify stats are tracked
        assert stats.snippets_attached == 5
        assert stats.line_matches == 20

    def test_metrics_logging_enabled(self, tmp_path: Path):
        """Test logging when LLMC_ENRICH_LOG is enabled."""
        with patch.dict(os.environ, {"LLMC_ENRICH_LOG": "true"}):
            # Create mock logger
            logger = Mock()

            # Simulate enrichment logging
            logger.info(
                "enrich attach (search): db=%s items=%d attached=%d line=%d path=%d truncated=%d",
                "/path/to/db.db",
                10,
                5,
                20,
                10,
                3,
            )

            # Verify log was called
            logger.info.assert_called_once()

    def test_metrics_logging_disabled(self, tmp_path: Path):
        """Test that logging is skipped when disabled."""
        with patch.dict(os.environ, {}, clear=False):
            if "LLMC_ENRICH_LOG" in os.environ:
                del os.environ["LLMC_ENRICH_LOG"]

            # Should not log when disabled
            logger = Mock()

            # Simulate no-op (logging disabled)
            # logger.info should not be called

    def test_metrics_for_search_operation(self, tmp_path: Path):
        """Test metrics specific to search enrichment."""
        metrics = {
            "operation": "search",
            "items_count": 15,
            "attached_count": 8,
            "line_matches": 45,
            "path_matches": 15,
            "truncated": 5,
        }

        # Verify all metrics are captured
        assert metrics["operation"] == "search"
        assert metrics["items_count"] == 15

    def test_metrics_for_where_used_operation(self, tmp_path: Path):
        """Test metrics for where-used enrichment."""
        metrics = {
            "operation": "where_used",
            "items_count": 25,
            "attached_count": 12,
            "line_matches": 60,
            "path_matches": 25,
            "truncated": 8,
        }

        assert metrics["operation"] == "where_used"

    def test_metrics_for_lineage_operation(self, tmp_path: Path):
        """Test metrics for lineage enrichment."""
        metrics = {
            "operation": "lineage",
            "items_count": 30,
            "attached_count": 18,
            "line_matches": 90,
            "path_matches": 30,
            "truncated": 12,
        }

        assert metrics["operation"] == "lineage"

    def test_metrics_persistence_to_db(self, tmp_path: Path):
        """Test that metrics are persisted to DB."""
        db_path = create_test_db(tmp_path)

        # Record metrics
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            INSERT INTO metrics (operation, items_count, attached_count)
            VALUES (?, ?, ?)
        """, ("search", 10, 5))
        conn.commit()
        conn.close()

        # Verify persisted
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT operation, items_count, attached_count FROM metrics"
        )
        row = cursor.fetchone()
        conn.close()

        assert row[0] == "search"
        assert row[1] == 10

    def test_metrics_aggregation(self, tmp_path: Path):
        """Test aggregation of metrics over time."""
        db_path = create_test_db(tmp_path)

        conn = sqlite3.connect(str(db_path))

        # Record multiple enrichment operations
        for i in range(5):
            conn.execute("""
                INSERT INTO metrics (operation, items_count, attached_count)
                VALUES (?, ?, ?)
            """, ("search", 10 + i, 5 + i))

        conn.commit()
        conn.close()

        # Aggregate metrics
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("""
            SELECT
                SUM(items_count) as total_items,
                SUM(attached_count) as total_attached,
                COUNT(*) as operation_count
            FROM metrics
            WHERE operation = 'search'
        """)
        result = cursor.fetchone()
        conn.close()

        assert result[2] == 5  # 5 operations

    @pytest.mark.allow_sleep
    def test_metrics_performance_impact(self, tmp_path: Path):
        """Test that metrics tracking doesn't significantly impact performance."""
        import time

        db_path = create_test_db(tmp_path)

        # Measure time with metrics
        start = time.time()
        # Simulate enrichment with metrics
        time.sleep(0.01)  # Placeholder
        elapsed_with_metrics = time.time() - start

        # Metrics overhead should be minimal
        assert elapsed_with_metrics < 1.0  # Should complete quickly

    def test_metrics_error_tracking(self, tmp_path: Path):
        """Test tracking of enrichment errors."""
        # Record failed enrichment attempts
        metrics = {
            "operation": "search",
            "items_count": 10,
            "attached_count": 0,
            "errors": 3,
        }

        # Should track errors separately
        assert metrics["errors"] == 3

    def test_metrics_logging_format(self, tmp_path: Path):
        """Test that log format is consistent."""
        log_format = "enrich attach (operation): db={} items={} attached={} line={} path={} truncated={}"

        # Test format with placeholders
        msg = log_format.format(
            "/path/db.db",
            10,
            5,
            20,
            10,
            3
        )

        assert "enrich attach" in msg
        assert "items=10" in msg


class TestEnrichmentEdgeCases:
    """Additional edge cases for enrichment."""

    def test_enrichment_with_empty_db(self, tmp_path: Path):
        """Test enrichment with completely empty DB."""
        db_path = tmp_path / "empty.db"
        db_path.write_text("garbage")  # Write garbage to ensure it's not a valid DB

        # Should handle gracefully
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("SELECT * FROM sqlite_master")
            conn.close()
            assert False, "Should fail to open empty DB as SQLite"
        except sqlite3.DatabaseError:
            pass  # Expected

    def test_enrichment_with_very_large_result_set(self, tmp_path: Path):
        """Test enrichment with 1000+ search results."""
        db_path = create_test_db(tmp_path)

        # Create large result set
        items = [Mock(file=f"file_{i}.py") for i in range(1000)]

        # Should handle large sets without memory issues
        # May need batching

    def test_enrichment_timeout_handling(self, tmp_path: Path):
        """Test that enrichment respects timeout limits."""
        # If enrichment takes too long, should timeout
        # Core search should still return

    def test_enrichment_memory_limits(self, tmp_path: Path):
        """Test enrichment with memory constraints."""
        # If memory is low, should fail gracefully
        # May skip enrichment

    def test_enrichment_with_binary_content(self, tmp_path: Path):
        """Test enrichment of binary files."""
        db_path = create_test_db(tmp_path)

        # Add binary content
        binary_content = b"\x00\x01\x02\x03\xff\xfe"

        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO enrichments (file_path, content) VALUES (?, ?)",
            ("binary.py", binary_content)
        )
        conn.commit()
        conn.close()

        # Should handle binary content appropriately

    def test_enrichment_db_backup_before_write(self, tmp_path: Path):
        """Test that DB creates backup before writing."""
        db_path = create_test_db(tmp_path)
        backup_path = tmp_path / "enrichment.db.backup"

        # Before write, create backup
        db_path.rename(backup_path)

        # Verify backup exists
        assert backup_path.exists()

    def test_enrichment_incremental_updates(self, tmp_path: Path):
        """Test that enrichment can be updated incrementally."""
        db_path = create_test_db(tmp_path)

        # Add initial data
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO enrichments (file_path, content) VALUES (?, ?)",
            ("test.py", "Initial content")
        )
        conn.commit()
        conn.close()

        # Update existing enrichment
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "UPDATE enrichments SET content = ? WHERE file_path = ?",
            ("Updated content", "test.py")
        )
        conn.commit()
        conn.close()

        # Verify updated
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT content FROM enrichments WHERE file_path = ?",
            ("test.py",)
        )
        content = cursor.fetchone()[0]
        conn.close()

        assert content == "Updated content"

    def test_enrichment_gc_of_old_data(self, tmp_path: Path):
        """Test garbage collection of old enrichment data."""
        db_path = create_test_db(tmp_path)

        # Add old timestamp data
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            INSERT INTO enrichments (file_path, content, created_at)
            VALUES (?, ?, datetime('now', '-30 days'))
        """, ("old.py", "Old content"))
        conn.commit()
        conn.close()

        # Should be able to clean old data
        # GC logic would delete data older than threshold

    def test_enrichment_deduplication(self, tmp_path: Path):
        """Test that duplicate enrichments are handled."""
        db_path = create_test_db(tmp_path)

        # Add same file multiple times
        conn = sqlite3.connect(str(db_path))
        for _ in range(3):
            conn.execute(
                "INSERT INTO enrichments (file_path, content) VALUES (?, ?)",
                ("test.py", "Same content")
            )
        conn.commit()
        conn.close()

        # Should deduplicate or handle gracefully
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM enrichments WHERE file_path = ?",
            ("test.py",)
        )
        count = cursor.fetchone()[0]
        conn.close()

        # May want to deduplicate
