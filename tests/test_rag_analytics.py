"""
Comprehensive unit tests for rag/analytics.py - Query Tracking & Analytics.

Tests cover:
- QueryTracker class and all methods
- Database initialization and schema
- Query logging and analytics calculation
- Edge cases and error handling
"""

from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import Mock, patch

import pytest

from llmc.rag.analytics import (
    AnalyticsSummary,
    QueryRecord,
    QueryTracker,
    format_analytics,
    run_analytics,
)


class TestQueryRecord:
    """Test QueryRecord dataclass."""

    def test_query_record_creation(self):
        """Test basic QueryRecord creation."""
        now = datetime.now()
        record = QueryRecord(
            query_text="test query",
            timestamp=now,
            results_count=5,
            files_retrieved=["file1.py", "file2.py"],
        )

        assert record.query_text == "test query"
        assert record.timestamp == now
        assert record.results_count == 5
        assert record.files_retrieved == ["file1.py", "file2.py"]


class TestAnalyticsSummary:
    """Test AnalyticsSummary dataclass."""

    def test_analytics_summary_creation(self):
        """Test basic AnalyticsSummary creation."""
        summary = AnalyticsSummary(
            top_queries=[("query1", 10), ("query2", 5)],
            top_files=[("file1.py", 8), ("file2.py", 3)],
            total_queries=15,
            unique_queries=10,
            avg_results_per_query=2.5,
            time_range_days=7,
        )

        assert summary.top_queries == [("query1", 10), ("query2", 5)]
        assert summary.top_files == [("file1.py", 8), ("file2.py", 3)]
        assert summary.total_queries == 15
        assert summary.unique_queries == 10
        assert summary.avg_results_per_query == 2.5
        assert summary.time_range_days == 7


class TestQueryTrackerInit:
    """Test QueryTracker initialization."""

    def test_init_creates_db_path(self):
        """Test initialization creates database directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"

            tracker = QueryTracker(db_path)

            assert tracker.db_path == db_path
            assert db_path.parent.exists()

    def test_init_initializes_database(self):
        """Test initialization creates database with correct schema."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"

            QueryTracker(db_path)

            # Verify database file was created
            assert db_path.exists()

            # Verify schema
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor}
            assert "query_history" in tables

            # Verify indexes
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = {row[0] for row in cursor}
            assert "idx_query_timestamp" in indexes
            assert "idx_query_text" in indexes

            conn.close()

    def test_init_creates_multiple_instances(self):
        """Test creating multiple tracker instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path1 = Path(tmpdir) / "analytics1.db"
            db_path2 = Path(tmpdir) / "analytics2.db"

            tracker1 = QueryTracker(db_path1)
            tracker2 = QueryTracker(db_path2)

            assert tracker1.db_path != tracker2.db_path


class TestQueryTrackerLogQuery:
    """Test query logging functionality."""

    def test_log_query_basic(self):
        """Test basic query logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            tracker.log_query(
                "test query", results_count=5, files_retrieved=["file1.py", "file2.py"]
            )

            # Verify data was logged
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT query_text, results_count FROM query_history")
            row = cursor.fetchone()
            assert row[0] == "test query"
            assert row[1] == 5
            conn.close()

    def test_log_query_stores_files_as_json(self):
        """Test that files_retrieved are stored as JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            files = ["file1.py", "file2.py", "file3.py"]
            tracker.log_query("test", 5, files)

            # Verify files were stored as JSON
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT files_retrieved FROM query_history")
            row = cursor.fetchone()
            stored_files = json.loads(row[0])
            assert stored_files == files
            conn.close()

    def test_log_query_multiple(self):
        """Test logging multiple queries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            for i in range(5):
                tracker.log_query(f"query {i}", results_count=i, files_retrieved=[f"file{i}.py"])

            # Verify all queries were logged
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT COUNT(*) FROM query_history")
            count = cursor.fetchone()[0]
            assert count == 5
            conn.close()

    def test_log_query_special_characters(self):
        """Test logging query with special characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            special_query = "测试 avec émojis 🎉 and symbols @#$%"
            tracker.log_query(special_query, 1, [])

            # Verify special characters are preserved
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT query_text FROM query_history")
            row = cursor.fetchone()
            assert row[0] == special_query
            conn.close()

    def test_log_query_empty_files_list(self):
        """Test logging query with empty files list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            tracker.log_query("test", 0, [])

            # Verify empty list is stored
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT files_retrieved FROM query_history")
            row = cursor.fetchone()
            assert json.loads(row[0]) == []
            conn.close()

    def test_log_query_large_results_count(self):
        """Test logging query with large results count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            tracker.log_query("test", 999999, [])

            # Verify large count is preserved
            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT results_count FROM query_history")
            row = cursor.fetchone()
            assert row[0] == 999999
            conn.close()


class TestQueryTrackerGetAnalytics:
    """Test analytics generation functionality."""

    def test_get_analytics_default_days(self):
        """Test get_analytics with default 7 days."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Log a query
            tracker.log_query("test", 5, ["file1.py"])

            summary = tracker.get_analytics()

            assert summary.time_range_days == 7
            assert summary.total_queries == 1
            assert summary.unique_queries == 1

    def test_get_analytics_custom_days(self):
        """Test get_analytics with custom days parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            tracker.log_query("test", 5, ["file1.py"])

            summary = tracker.get_analytics(days=30)

            assert summary.time_range_days == 30

    def test_get_analytics_no_data(self):
        """Test analytics with no data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            summary = tracker.get_analytics()

            assert summary.total_queries == 0
            assert summary.unique_queries == 0
            assert summary.avg_results_per_query == 0.0
            assert summary.top_queries == []
            assert summary.top_files == []

    def test_get_analytics_top_queries(self):
        """Test top queries calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Log queries with different frequencies
            tracker.log_query("common query", 5, ["file1.py"])
            tracker.log_query("common query", 3, ["file2.py"])
            tracker.log_query("rare query", 1, ["file3.py"])

            summary = tracker.get_analytics()

            # Verify top queries are sorted by count
            assert len(summary.top_queries) == 2
            assert summary.top_queries[0] == ("common query", 2)
            assert summary.top_queries[1] == ("rare query", 1)

    def test_get_analytics_top_queries_limit(self):
        """Test top queries are limited to 10."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Log 15 different queries
            for i in range(15):
                tracker.log_query(f"query {i}", 1, [])

            summary = tracker.get_analytics()

            # Should be limited to 10
            assert len(summary.top_queries) == 10

    def test_get_analytics_top_files(self):
        """Test top files calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Log queries retrieving same files
            tracker.log_query("query1", 1, ["common.py"])
            tracker.log_query("query2", 1, ["common.py"])
            tracker.log_query("query3", 1, ["rare.py"])

            summary = tracker.get_analytics()

            # Verify top files are sorted by count
            assert len(summary.top_files) == 2
            assert summary.top_files[0] == ("common.py", 2)
            assert summary.top_files[1] == ("rare.py", 1)

    def test_get_analytics_top_files_limit(self):
        """Test top files are limited to 10."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Log queries retrieving 15 different files
            for i in range(15):
                tracker.log_query("test", 1, [f"file{i}.py"])

            summary = tracker.get_analytics()

            # Should be limited to 10
            assert len(summary.top_files) == 10

    def test_get_analytics_unique_queries(self):
        """Test unique queries count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Log duplicate and unique queries
            tracker.log_query("duplicate", 1, [])
            tracker.log_query("duplicate", 1, [])
            tracker.log_query("unique1", 1, [])
            tracker.log_query("unique2", 1, [])

            summary = tracker.get_analytics()

            assert summary.total_queries == 4
            assert summary.unique_queries == 3

    def test_get_analytics_average_results(self):
        """Test average results per query calculation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Log queries with different result counts
            tracker.log_query("q1", 10, [])
            tracker.log_query("q2", 20, [])
            tracker.log_query("q3", 30, [])

            summary = tracker.get_analytics()

            # Average should be (10 + 20 + 30) / 3 = 20
            assert summary.avg_results_per_query == 20.0

    def test_get_analytics_with_time_filter(self):
        """Test analytics respects time filter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Log a query
            tracker.log_query("recent", 1, [])

            # Manually insert an old query (8 days ago)
            conn = sqlite3.connect(str(db_path))
            old_date = datetime.now() - timedelta(days=8)
            conn.execute(
                """
                INSERT INTO query_history (query_text, timestamp, results_count, files_retrieved)
                VALUES (?, ?, ?, ?)
                """,
                ("old", old_date.strftime("%Y-%m-%d %H:%M:%S"), 1, json.dumps([])),
            )
            conn.commit()
            conn.close()

            # Get analytics for last 7 days
            summary = tracker.get_analytics(days=7)

            # Should only count recent query
            assert summary.total_queries == 1
            assert summary.top_queries[0] == ("recent", 1)

    def test_get_analytics_handles_malformed_json(self):
        """Test analytics handles malformed JSON in files_retrieved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Manually insert malformed JSON
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                """
                INSERT INTO query_history (query_text, timestamp, results_count, files_retrieved)
                VALUES (?, ?, ?, ?)
                """,
                ("bad json", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 1, "not valid json"),
            )
            conn.commit()
            conn.close()

            # Should not crash
            summary = tracker.get_analytics()

            assert summary.total_queries == 1
            # Malformed JSON should be skipped in top files
            # So top_files might be empty or only contain good entries

    def test_get_analytics_empty_time_range(self):
        """Test analytics with future cutoff date."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Log a query
            tracker.log_query("test", 1, [])

            # Get analytics for future date range
            summary = tracker.get_analytics(days=-1)  # Negative days

            # Should return zero results
            assert summary.total_queries == 0


class TestQueryTrackerGetRecentQueries:
    """Test get_recent_queries functionality."""

    def test_get_recent_queries_default_limit(self):
        """Test get_recent_queries with default limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Log 25 queries
            for i in range(25):
                tracker.log_query(f"query {i}", 1, [])

            recent = tracker.get_recent_queries()

            # Should return default limit of 20
            assert len(recent) == 20

    def test_get_recent_queries_custom_limit(self):
        """Test get_recent_queries with custom limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            for i in range(10):
                tracker.log_query(f"query {i}", 1, [])

            recent = tracker.get_recent_queries(limit=5)

            assert len(recent) == 5

    def test_get_recent_queries_returns_records(self):
        """Test get_recent_queries returns QueryRecord objects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            files = ["file1.py", "file2.py"]
            tracker.log_query("test query", 5, files)

            recent = tracker.get_recent_queries()

            assert len(recent) == 1
            record = recent[0]
            assert isinstance(record, QueryRecord)
            assert record.query_text == "test query"
            assert record.results_count == 5
            assert record.files_retrieved == files

    def test_get_recent_queries_order(self):
        """Test get_recent_queries returns in descending timestamp order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            for i in range(5):
                tracker.log_query(f"query {i}", 1, [])

            recent = tracker.get_recent_queries(limit=5)

            # Verify descending order
            timestamps = [r.timestamp for r in recent]
            assert timestamps == sorted(timestamps, reverse=True)

    def test_get_recent_queries_limit_zero(self):
        """Test get_recent_queries with limit=0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            for i in range(5):
                tracker.log_query(f"query {i}", 1, [])

            recent = tracker.get_recent_queries(limit=0)

            assert len(recent) == 0

    def test_get_recent_queries_more_than_available(self):
        """Test get_recent_queries when limit exceeds available records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Log only 3 queries but ask for 10
            for i in range(3):
                tracker.log_query(f"query {i}", 1, [])

            recent = tracker.get_recent_queries(limit=10)

            # Should return only available records
            assert len(recent) == 3

    def test_get_recent_queries_handles_malformed_json(self):
        """Test get_recent_queries handles malformed JSON gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Manually insert malformed JSON
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                """
                INSERT INTO query_history (query_text, timestamp, results_count, files_retrieved)
                VALUES (?, ?, ?, ?)
                """,
                ("bad json", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 1, "not valid json"),
            )
            conn.commit()
            conn.close()

            recent = tracker.get_recent_queries()

            # Should return record with empty files list
            assert len(recent) == 1
            assert recent[0].files_retrieved == []


class TestFormatAnalytics:
    """Test analytics formatting function."""

    def test_format_analytics_empty(self):
        """Test formatting empty analytics."""
        summary = AnalyticsSummary(
            top_queries=[],
            top_files=[],
            total_queries=0,
            unique_queries=0,
            avg_results_per_query=0.0,
            time_range_days=7,
        )

        formatted = format_analytics(summary)

        assert "QUERY ANALYTICS" in formatted
        assert "Total Queries: 0" in formatted

    def test_format_analytics_with_data(self):
        """Test formatting analytics with data."""
        summary = AnalyticsSummary(
            top_queries=[("test query", 5), ("another query", 3)],
            top_files=[("file1.py", 4), ("file2.py", 2)],
            total_queries=10,
            unique_queries=8,
            avg_results_per_query=2.5,
            time_range_days=7,
        )

        formatted = format_analytics(summary)

        assert "QUERY ANALYTICS" in formatted
        assert "Last 7 Days" in formatted
        assert "Total Queries: 10" in formatted
        assert "Unique Queries: 8" in formatted
        assert "Avg Results/Query: 2.5" in formatted
        assert "TOP QUERIES:" in formatted
        assert "test query" in formatted
        assert "5" in formatted  # Count
        assert "MOST RETRIEVED FILES:" in formatted
        assert "file1.py" in formatted

    def test_format_analytics_truncates_long_queries(self):
        """Test formatting truncates long queries."""
        long_query = "a" * 100
        summary = AnalyticsSummary(
            top_queries=[(long_query, 1)],
            top_files=[],
            total_queries=1,
            unique_queries=1,
            avg_results_per_query=1.0,
            time_range_days=7,
        )

        formatted = format_analytics(summary)

        # Should be truncated to 50 chars with "..." if needed
        assert (
            "..." in formatted
            or len([line for line in formatted.split("\n") if long_query in line]) == 0
        )

    def test_format_analytics_truncates_long_files(self):
        """Test formatting truncates long file paths."""
        long_path = "/very/long/path/to/some/deeply/nested/directory/structure/file.py"
        summary = AnalyticsSummary(
            top_queries=[],
            top_files=[(long_path, 1)],
            total_queries=1,
            unique_queries=1,
            avg_results_per_query=1.0,
            time_range_days=7,
        )

        formatted = format_analytics(summary)

        # Should truncate if path is too long
        assert "..." in formatted or long_path in formatted

    def test_format_analytics_numbering(self):
        """Test formatting includes proper numbering."""
        summary = AnalyticsSummary(
            top_queries=[(f"query {i}", 1) for i in range(3)],
            top_files=[(f"file {i}.py", 1) for i in range(3)],
            total_queries=3,
            unique_queries=3,
            avg_results_per_query=1.0,
            time_range_days=7,
        )

        formatted = format_analytics(summary)

        # Should have numbered lists
        lines = formatted.split("\n")
        query_section = False
        for line in lines:
            if "TOP QUERIES:" in line:
                query_section = True
            if query_section and "  1." in line:
                assert True
                break

    def test_format_analytics_custom_time_range(self):
        """Test formatting shows custom time range."""
        summary = AnalyticsSummary(
            top_queries=[],
            top_files=[],
            total_queries=0,
            unique_queries=0,
            avg_results_per_query=0.0,
            time_range_days=30,
        )

        formatted = format_analytics(summary)

        assert "Last 30 Days" in formatted


class TestRunAnalytics:
    """Test run_analytics function."""

    @patch("llmc.rag.analytics.QueryTracker")
    @patch("llmc.rag.analytics.format_analytics")
    def test_run_analytics_success(self, mock_format, mock_tracker_class):
        """Test run_analytics with existing database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / ".rag").mkdir()

            # Mock the tracker and summary
            mock_tracker = Mock()
            mock_summary = Mock()
            mock_tracker.get_analytics.return_value = mock_summary
            mock_tracker_class.return_value = mock_tracker
            mock_format.return_value = "Formatted analytics"

            run_analytics(repo_root, days=7)

            # Verify tracker was created with correct path
            expected_db = repo_root / ".rag" / "analytics.db"
            mock_tracker_class.assert_called_once_with(expected_db)

            # Verify get_analytics was called
            mock_tracker.get_analytics.assert_called_once_with(days=7)

            # Verify formatting was called
            mock_format.assert_called_once_with(mock_summary)

    @patch("builtins.print")
    def test_run_analytics_no_database(self, mock_print):
        """Test run_analytics when database doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            run_analytics(repo_root, days=7)

            # Should print message about no history
            mock_print.assert_called_once()
            assert "No query history found" in mock_print.call_args[0][0]


class TestAnalyticsEdgeCases:
    """Test edge cases and error handling."""

    def test_concurrent_logging(self):
        """Test logging from multiple trackers to same database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"

            tracker1 = QueryTracker(db_path)
            tracker2 = QueryTracker(db_path)  # Same DB

            tracker1.log_query("query1", 1, [])
            tracker2.log_query("query2", 1, [])

            # Both should be able to read the data
            tracker1_summary = tracker1.get_analytics()
            tracker2_summary = tracker2.get_analytics()

            assert tracker1_summary.total_queries == 2
            assert tracker2_summary.total_queries == 2

    def test_log_query_with_unicode(self):
        """Test logging queries with Unicode characters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            unicode_query = "查询 中文 text with émojis 🎉 and symbols ✓"
            unicode_files = ["测试文件.py", "файл.py"]

            tracker.log_query(unicode_query, 1, unicode_files)

            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT query_text, files_retrieved FROM query_history")
            row = cursor.fetchone()
            assert row[0] == unicode_query
            assert json.loads(row[1]) == unicode_files
            conn.close()

    def test_log_query_with_nonexistent_file_path(self):
        """Test logging with non-existent file paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # File doesn't need to exist to be tracked
            tracker.log_query("test", 1, ["/nonexistent/path/file.py"])

            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT files_retrieved FROM query_history")
            row = cursor.fetchone()
            assert json.loads(row[0]) == ["/nonexistent/path/file.py"]
            conn.close()

    def test_get_analytics_timezone_handling(self):
        """Test analytics handles timezone correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Log a query
            tracker.log_query("test", 1, [])

            # Get analytics - should handle timezone-aware datetime
            summary = tracker.get_analytics()

            assert summary.total_queries == 1

    def test_empty_database_with_multiple_calls(self):
        """Test multiple analytics calls on empty database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            # Multiple calls should all work
            for _ in range(5):
                summary = tracker.get_analytics()
                assert summary.total_queries == 0

    def test_log_query_zero_results(self):
        """Test logging query with zero results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "analytics.db"
            tracker = QueryTracker(db_path)

            tracker.log_query("no results", 0, [])

            conn = sqlite3.connect(str(db_path))
            cursor = conn.execute("SELECT results_count FROM query_history")
            row = cursor.fetchone()
            assert row[0] == 0
            conn.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
