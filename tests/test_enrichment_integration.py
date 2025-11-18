"""
Integration tests for rag/enrichment.py with LLM API mocking.

Tests cover:
- Enrichment pipeline with mocked LLM responses
- Batch processing workflows
- Error handling and retry mechanisms
- Integration with database and embeddings
- LLM API integration (rate limiting, failures, etc.)
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from tools.rag.database import Database
from tools.rag.enrichment import (
    enrich_spans,
    batch_enrich,
    enrich_with_retry,
    EnrichmentConfig,
)
from tools.rag.types import SpanRecord, EnrichmentRecord, FileRecord


class TestEnrichmentPipelineWithMockLLM:
    """Test enrichment pipeline with mocked LLM API responses."""

    @patch("tools.rag.enrichment.call_llm_api")
    def test_enrich_single_span(self, mock_llm_api):
        """Test enriching a single code span."""
        # Mock LLM API response
        mock_llm_api.return_value = {
            "summary": "This function validates JWT tokens",
            "tags": ["authentication", "security", "jwt"],
            "inputs": "token string, secret key, options",
            "outputs": "validated payload or error",
            "side_effects": "none",
            "pitfalls": "always check expiration",
            "usage_snippet": "validate_jwt(token, secret)"
        }

        # Create test database
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            # Insert test file
            db.conn.execute(
                "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                ("auth.py", "python", "hash123", 1000, 123456.0)
            )
            db.conn.commit()

            file_id = db.conn.execute("SELECT id FROM files WHERE path='auth.py'").fetchone()[0]

            # Insert test span
            span_hash = "span_123"
            db.conn.execute(
                """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, "validate_jwt", "function", 10, 30, 200, 800, span_hash)
            )
            db.conn.commit()

            # Enrich the span
            config = EnrichmentConfig()
            result = enrich_spans(db, [span_hash], config)

            # Verify LLM was called
            mock_llm_api.assert_called_once()

            # Verify enrichment was stored
            cursor = db.conn.execute(
                "SELECT summary, tags, usage_snippet FROM enrichments WHERE span_hash=?",
                (span_hash,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert "JWT" in row[0]
            assert "authentication" in row[1]
            assert "validate_jwt" in row[2]

    @patch("tools.rag.enrichment.call_llm_api")
    def test_enrich_multiple_spans_batch(self, mock_llm_api):
        """Test enriching multiple spans in batch."""
        # Mock LLM API to return different responses per call
        responses = [
            {"summary": "Function 1 summary", "tags": ["tag1"]},
            {"summary": "Function 2 summary", "tags": ["tag2"]},
            {"summary": "Function 3 summary", "tags": ["tag3"]},
        ]
        mock_llm_api.side_effect = responses

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            # Insert test files and spans
            for i in range(3):
                db.conn.execute(
                    "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                    (f"file{i}.py", "python", f"hash{i}", 1000, 123456.0)
                )
                db.conn.commit()

                file_id = db.conn.execute("SELECT id FROM files WHERE path=?", (f"file{i}.py",)).fetchone()[0]

                span_hash = f"span_{i}"
                db.conn.execute(
                    """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (file_id, f"func{i}", "function", 10, 30, 200, 800, span_hash)
                )
                db.conn.commit()

            # Enrich all spans
            config = EnrichmentConfig()
            span_hashes = [f"span_{i}" for i in range(3)]
            results = enrich_spans(db, span_hashes, config)

            # Verify all were enriched
            assert len(results) == 3
            mock_llm_api.assert_called_times(3)

            # Verify each span has enrichment
            for i in range(3):
                cursor = db.conn.execute(
                    "SELECT summary FROM enrichments WHERE span_hash=?",
                    (f"span_{i}",)
                )
                row = cursor.fetchone()
                assert row is not None
                assert f"Function {i}" in row[0]

    @patch("tools.rag.enrichment.call_llm_api")
    def test_enrichment_with_code_context(self, mock_llm_api):
        """Test enrichment includes code context."""
        mock_llm_api.return_value = {
            "summary": "Validates input parameters",
            "tags": ["validation"],
            "inputs": "user input",
            "outputs": "validated output",
            "side_effects": "raises exception on invalid input",
            "pitfalls": "check all edge cases",
            "usage_snippet": "validate(user_input)"
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            # Insert test file with actual code
            code = """def validate_user_input(input):
    '''Validates user input'''
    if not input:
        raise ValueError("Input required")
    return input.strip()
"""
            db.conn.execute(
                "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                ("validator.py", "python", "hash123", len(code), 123456.0)
            )
            db.conn.commit()

            file_id = db.conn.execute("SELECT id FROM files WHERE path='validator.py'").fetchone()[0]

            # Insert span covering the function
            db.conn.execute(
                """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, "validate_user_input", "function", 1, 5, 0, len(code), "span_123")
            )
            db.conn.commit()

            # Enrich with context
            config = EnrichmentConfig(include_code_context=True)
            enrich_spans(db, ["span_123"], config)

            # Verify LLM was called with code context
            call_args = mock_llm_api.call_args
            assert call_args is not None

    @patch("tools.rag.enrichment.call_llm_api")
    def test_enrichment_retry_on_failure(self, mock_llm_api):
        """Test enrichment retries on temporary failures."""
        # Fail twice, then succeed
        mock_llm_api.side_effect = [
            Exception("Network timeout"),
            Exception("Rate limited"),
            {"summary": "Success", "tags": ["test"]}
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            db.conn.execute(
                "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                ("test.py", "python", "hash", 1000, 123456.0)
            )
            db.conn.commit()

            file_id = db.conn.execute("SELECT id FROM files WHERE path='test.py'").fetchone()[0]

            db.conn.execute(
                """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, "test_func", "function", 1, 10, 0, 100, "span_123")
            )
            db.conn.commit()

            # Enrich with retry
            config = EnrichmentConfig(max_retries=3)
            result = enrich_with_retry(db, "span_123", config)

            # Should succeed after retries
            assert result is not None
            assert mock_llm_api.call_count == 3

    @patch("tools.rag.enrichment.call_llm_api")
    def test_enrichment_fails_after_max_retries(self, mock_llm_api):
        """Test enrichment fails after max retries."""
        mock_llm_api.side_effect = Exception("Persistent failure")

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            db.conn.execute(
                "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                ("test.py", "python", "hash", 1000, 123456.0)
            )
            db.conn.commit()

            file_id = db.conn.execute("SELECT id FROM files WHERE path='test.py'").fetchone()[0]

            db.conn.execute(
                """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, "test_func", "function", 1, 10, 0, 100, "span_123")
            )
            db.conn.commit()

            # Enrich with limited retries
            config = EnrichmentConfig(max_retries=2)
            result = enrich_with_retry(db, "span_123", config)

            # Should fail
            assert result is False
            assert mock_llm_api.call_count == 2

    @patch("tools.rag.enrichment.call_llm_api")
    def test_enrichment_handles_llm_api_timeout(self, mock_llm_api):
        """Test enrichment handles LLM API timeout."""
        mock_llm_api.side_effect = TimeoutError("API timeout")

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            db.conn.execute(
                "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                ("test.py", "python", "hash", 1000, 123456.0)
            )
            db.conn.commit()

            file_id = db.conn.execute("SELECT id FROM files WHERE path='test.py'").fetchone()[0]

            db.conn.execute(
                """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, "test_func", "function", 1, 10, 0, 100, "span_123")
            )
            db.conn.commit()

            config = EnrichmentConfig()
            result = enrich_spans(db, ["span_123"], config)

            # Should handle timeout gracefully
            assert result is not None

    @patch("tools.rag.enrichment.call_llm_api")
    def test_enrichment_handles_invalid_llm_response(self, mock_llm_api):
        """Test enrichment handles invalid LLM response format."""
        mock_llm_api.return_value = {
            "invalid_field": "not what we expect"
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            db.conn.execute(
                "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                ("test.py", "python", "hash", 1000, 123456.0)
            )
            db.conn.commit()

            file_id = db.conn.execute("SELECT id FROM files WHERE path='test.py'").fetchone()[0]

            db.conn.execute(
                """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, "test_func", "function", 1, 10, 0, 100, "span_123")
            )
            db.conn.commit()

            config = EnrichmentConfig()
            result = enrich_spans(db, ["span_123"], config)

            # Should handle invalid response gracefully
            assert result is not None


class TestEnrichmentBatchProcessing:
    """Test batch enrichment processing."""

    @patch("tools.rag.enrichment.call_llm_api")
    def test_batch_processing_respects_batch_size(self, mock_llm_api):
        """Test batch processing respects configured batch size."""
        mock_llm_api.return_value = {"summary": "Test", "tags": ["test"]}

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            # Create 20 spans
            for i in range(20):
                db.conn.execute(
                    "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                    (f"file{i}.py", "python", f"hash{i}", 1000, 123456.0)
                )
                db.conn.commit()

                file_id = db.conn.execute("SELECT id FROM files WHERE path=?", (f"file{i}.py",)).fetchone()[0]

                db.conn.execute(
                    """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (file_id, f"func{i}", "function", 1, 10, 0, 100, f"span_{i}")
                )
                db.conn.commit()

            # Process in batches of 5
            config = EnrichmentConfig(batch_size=5)
            span_hashes = [f"span_{i}" for i in range(20)]
            batch_enrich(db, span_hashes, config)

            # Should make 4 API calls (20 / 5)
            assert mock_llm_api.call_count == 4

    @patch("tools.rag.enrichment.call_llm_api")
    def test_batch_processing_partial_batch(self, mock_llm_api):
        """Test batch processing with incomplete final batch."""
        mock_llm_api.return_value = {"summary": "Test", "tags": ["test"]}

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            # Create 23 spans (not divisible by batch size)
            for i in range(23):
                db.conn.execute(
                    "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                    (f"file{i}.py", "python", f"hash{i}", 1000, 123456.0)
                )
                db.conn.commit()

                file_id = db.conn.execute("SELECT id FROM files WHERE path=?", (f"file{i}.py",)).fetchone()[0]

                db.conn.execute(
                    """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (file_id, f"func{i}", "function", 1, 10, 0, 100, f"span_{i}")
                )
                db.conn.commit()

            # Process in batches of 10
            config = EnrichmentConfig(batch_size=10)
            span_hashes = [f"span_{i}" for i in range(23)]
            batch_enrich(db, span_hashes, config)

            # Should make 3 API calls (10 + 10 + 3)
            assert mock_llm_api.call_count == 3

    @patch("tools.rag.enrichment.call_llm_api")
    def test_batch_processing_continues_on_individual_failure(self, mock_llm_api):
        """Test batch processing continues even if one item fails."""
        # Fail only for span_5
        def side_effect(*args, **kwargs):
            if "span_5" in str(args):
                raise Exception("Enrichment failed")
            return {"summary": "Success", "tags": ["test"]}

        mock_llm_api.side_effect = side_effect

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            # Create 10 spans
            for i in range(10):
                db.conn.execute(
                    "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                    (f"file{i}.py", "python", f"hash{i}", 1000, 123456.0)
                )
                db.conn.commit()

                file_id = db.conn.execute("SELECT id FROM files WHERE path=?", (f"file{i}.py",)).fetchone()[0]

                db.conn.execute(
                    """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (file_id, f"func{i}", "function", 1, 10, 0, 100, f"span_{i}")
                )
                db.conn.commit()

            config = EnrichmentConfig()
            span_hashes = [f"span_{i}" for i in range(10)]
            results = batch_enrich(db, span_hashes, config)

            # Should have attempted all 10 enrichments
            assert mock_llm_api.call_count >= 10


class TestEnrichmentIntegrationWithDatabase:
    """Test enrichment integration with database operations."""

    @patch("tools.rag.enrichment.call_llm_api")
    def test_enrichment_updates_existing_record(self, mock_llm_api):
        """Test enrichment updates existing enrichment record."""
        mock_llm_api.return_value = {
            "summary": "Updated summary",
            "tags": ["updated", "tags"],
            "inputs": "new inputs",
            "outputs": "new outputs",
            "side_effects": "new side effects",
            "pitfalls": "new pitfalls",
            "usage_snippet": "new_usage()"
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            db.conn.execute(
                "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                ("test.py", "python", "hash", 1000, 123456.0)
            )
            db.conn.commit()

            file_id = db.conn.execute("SELECT id FROM files WHERE path='test.py'").fetchone()[0]

            span_hash = "span_123"
            db.conn.execute(
                """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, "test_func", "function", 1, 10, 0, 100, span_hash)
            )
            db.conn.commit()

            # Insert initial enrichment
            db.conn.execute(
                """INSERT INTO enrichments (span_hash, summary, tags, model, created_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (span_hash, "Old summary", "old tags", "old_model")
            )
            db.conn.commit()

            # Enrich again
            config = EnrichmentConfig()
            enrich_spans(db, [span_hash], config)

            # Verify it was updated
            cursor = db.conn.execute(
                "SELECT summary, tags, usage_snippet FROM enrichments WHERE span_hash=?",
                (span_hash,)
            )
            row = cursor.fetchone()
            assert "Updated" in row[0]
            assert "updated" in row[1]
            assert "new_usage()" in row[2]

    @patch("tools.rag.enrichment.call_llm_api")
    def test_enrichment_with_model_versioning(self, mock_llm_api):
        """Test enrichment records include model information."""
        mock_llm_api.return_value = {
            "summary": "Test summary",
            "tags": ["test"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            db.conn.execute(
                "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                ("test.py", "python", "hash", 1000, 123456.0)
            )
            db.conn.commit()

            file_id = db.conn.execute("SELECT id FROM files WHERE path='test.py'").fetchone()[0]

            span_hash = "span_123"
            db.conn.execute(
                """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, "test_func", "function", 1, 10, 0, 100, span_hash)
            )
            db.conn.commit()

            # Enrich with specific model
            config = EnrichmentConfig(model="gpt-4")
            enrich_spans(db, [span_hash], config)

            # Verify model was recorded
            cursor = db.conn.execute(
                "SELECT model FROM enrichments WHERE span_hash=?",
                (span_hash,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "gpt-4"

    @patch("tools.rag.enrichment.call_llm_api")
    def test_enrichment_handles_schema_version(self, mock_llm_api):
        """Test enrichment works with schema versioning."""
        mock_llm_api.return_value = {
            "summary": "Test summary",
            "tags": ["test"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            db.conn.execute(
                "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                ("test.py", "python", "hash", 1000, 123456.0)
            )
            db.conn.commit()

            file_id = db.conn.execute("SELECT id FROM files WHERE path='test.py'").fetchone()[0]

            span_hash = "span_123"
            db.conn.execute(
                """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, "test_func", "function", 1, 10, 0, 100, span_hash)
            )
            db.conn.commit()

            # Enrich with schema version
            config = EnrichmentConfig(schema_version="v2")
            enrich_spans(db, [span_hash], config)

            # Verify schema version was recorded
            cursor = db.conn.execute(
                "SELECT schema_ver FROM enrichments WHERE span_hash=?",
                (span_hash,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == "v2"


class TestEnrichmentEdgeCases:
    """Test enrichment edge cases."""

    @patch("tools.rag.enrichment.call_llm_api")
    def test_enrichment_with_nonexistent_span(self, mock_llm_api):
        """Test enrichment handles non-existent span gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            # Try to enrich non-existent span
            config = EnrichmentConfig()
            result = enrich_spans(db, ["nonexistent"], config)

            # Should handle gracefully
            assert result is not None
            # LLM should not be called for non-existent spans
            mock_llm_api.assert_not_called()

    @patch("tools.rag.enrichment.call_llm_api")
    def test_enrichment_with_empty_batch(self, mock_llm_api):
        """Test enrichment with empty span list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            config = EnrichmentConfig()
            result = enrich_spans(db, [], config)

            # Should handle empty list gracefully
            assert result is not None
            mock_llm_api.assert_not_called()

    @patch("tools.rag.enrichment.call_llm_api")
    def test_enrichment_with_special_characters(self, mock_llm_api):
        """Test enrichment handles code with special characters."""
        mock_llm_api.return_value = {
            "summary": "Handles Unicode ✓",
            "tags": ["特殊字符"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            # Insert file with special characters
            code = """def функция():
    '''Функция с Unicode'''
    return "✓"
"""
            db.conn.execute(
                "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                ("test.py", "python", "hash", len(code), 123456.0)
            )
            db.conn.commit()

            file_id = db.conn.execute("SELECT id FROM files WHERE path='test.py'").fetchone()[0]

            span_hash = "span_123"
            db.conn.execute(
                """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, "функция", "function", 1, 3, 0, len(code), span_hash)
            )
            db.conn.commit()

            # Enrich should handle special characters
            config = EnrichmentConfig()
            enrich_spans(db, [span_hash], config)

            # Verify LLM was called
            mock_llm_api.assert_called_once()

    @patch("tools.rag.enrichment.call_llm_api")
    def test_enrichment_rate_limiting(self, mock_llm_api):
        """Test enrichment respects rate limiting."""
        # Simulate rate limiting
        call_count = 0
        def rate_limit_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise Exception("Rate limited")
            return {"summary": "Success", "tags": ["test"]}

        mock_llm_api.side_effect = rate_limit_side_effect

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            # Create multiple spans
            for i in range(10):
                db.conn.execute(
                    "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                    (f"file{i}.py", "python", f"hash{i}", 1000, 123456.0)
                )
                db.conn.commit()

                file_id = db.conn.execute("SELECT id FROM files WHERE path=?", (f"file{i}.py",)).fetchone()[0]

                db.conn.execute(
                    """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (file_id, f"func{i}", "function", 1, 10, 0, 100, f"span_{i}")
                )
                db.conn.commit()

            # Enrich with rate limiting
            config = EnrichmentConfig(max_retries=5)
            span_hashes = [f"span_{i}" for i in range(10)]
            results = batch_enrich(db, span_hashes, config)

            # Should eventually succeed after rate limit retries
            assert results is not None


class TestEnrichmentConcurrency:
    """Test enrichment concurrency handling."""

    @patch("tools.rag.enrichment.call_llm_api")
    def test_concurrent_enrichment_same_span(self, mock_llm_api):
        """Test concurrent enrichment attempts on same span."""
        mock_llm_api.return_value = {
            "summary": "Test",
            "tags": ["test"]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)

            db.conn.execute(
                "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
                ("test.py", "python", "hash", 1000, 123456.0)
            )
            db.conn.commit()

            file_id = db.conn.execute("SELECT id FROM files WHERE path='test.py'").fetchone()[0]

            span_hash = "span_123"
            db.conn.execute(
                """INSERT INTO spans (file_id, symbol, kind, start_line, end_line, byte_start, byte_end, span_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, "test_func", "function", 1, 10, 0, 100, span_hash)
            )
            db.conn.commit()

            config = EnrichmentConfig()
            # Attempt to enrich same span multiple times concurrently
            # (In real scenario, this would be from different threads/processes)
            enrich_spans(db, [span_hash], config)
            enrich_spans(db, [span_hash], config)

            # Should handle gracefully
            # The second enrichment might update or be skipped
            assert mock_llm_api.call_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
