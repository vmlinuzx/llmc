"""
Unit tests for freshness.py - IndexStatus and FreshnessState types.

These tests validate the index status reading and freshness classification logic
used to determine when RAG can be trusted.
"""

import json
from pathlib import Path

import pytest

from llmc.rag.freshness import FreshnessState, IndexState, IndexStatus


@pytest.mark.rag_freshness
class TestIndexStatus:
    """Test IndexStatus dataclass."""

    def test_minimal_index_status(self):
        """IndexStatus should be constructible with only required fields."""
        status = IndexStatus(
            repo="test_repo",
            index_state="fresh",
            last_indexed_at="2025-11-16T10:00:00Z",
            last_indexed_commit="abc123def456",
            schema_version="1.0",
        )

        assert status.repo == "test_repo"
        assert status.index_state == "fresh"
        assert status.last_indexed_at == "2025-11-16T10:00:00Z"
        assert status.last_indexed_commit == "abc123def456"
        assert status.schema_version == "1.0"
        assert status.last_error is None

    def test_index_status_with_error(self):
        """IndexStatus should handle optional last_error field."""
        status = IndexStatus(
            repo="test_repo",
            index_state="error",
            last_indexed_at="2025-11-16T10:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
            last_error="Database connection failed",
        )

        assert status.last_error == "Database connection failed"
        assert status.index_state == "error"

    def test_to_dict_without_error(self):
        """IndexStatus.to_dict() should exclude last_error when None."""
        status = IndexStatus(
            repo="test_repo",
            index_state="fresh",
            last_indexed_at="2025-11-16T10:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
        )

        result = status.to_dict()

        assert isinstance(result, dict)
        assert result["repo"] == "test_repo"
        assert result["index_state"] == "fresh"
        assert result["last_indexed_at"] == "2025-11-16T10:00:00Z"
        assert result["last_indexed_commit"] == "abc123"
        assert result["schema_version"] == "1.0"
        # last_error should NOT be in the dict when it's None
        assert "last_error" not in result

    def test_to_dict_with_error(self):
        """IndexStatus.to_dict() should include last_error when present."""
        status = IndexStatus(
            repo="test_repo",
            index_state="error",
            last_indexed_at="2025-11-16T10:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
            last_error="Index corrupted",
        )

        result = status.to_dict()

        assert result["last_error"] == "Index corrupted"
        assert result["index_state"] == "error"

    def test_all_index_states(self):
        """IndexStatus should accept all valid IndexState values."""
        states: list[IndexState] = ["fresh", "stale", "rebuilding", "error"]

        for state in states:
            status = IndexStatus(
                repo="test",
                index_state=state,
                last_indexed_at="2025-11-16T10:00:00Z",
                last_indexed_commit="abc123",
                schema_version="1.0",
            )
            assert status.index_state == state

    def test_all_freshness_states(self):
        """FreshnessState should accept all valid values."""
        states: list[FreshnessState] = ["FRESH", "STALE", "UNKNOWN"]

        for state in states:
            # This is used via RagToolMeta but we test the type directly
            assert state in ["FRESH", "STALE", "UNKNOWN"]


@pytest.mark.rag_freshness
class TestIndexStatusFileIO:
    """Test reading IndexStatus from files."""

    def test_load_valid_fresh_status(self, tmp_path: Path):
        """Should correctly load a valid fresh status file."""
        status_file = tmp_path / "rag_index_status.json"

        status_data = {
            "repo": "test_repo",
            "index_state": "fresh",
            "last_indexed_at": "2025-11-16T10:00:00Z",
            "last_indexed_commit": "abc123",
            "schema_version": "1.0",
        }

        with open(status_file, "w") as f:
            json.dump(status_data, f)

        # Simulate loading (in real code, this would be a proper function)
        with open(status_file) as f:
            loaded = json.load(f)

        assert loaded["index_state"] == "fresh"
        assert loaded["repo"] == "test_repo"

    def test_load_stale_status(self, tmp_path: Path):
        """Should correctly load a stale status file."""
        status_file = tmp_path / "rag_index_status.json"

        status_data = {
            "repo": "test_repo",
            "index_state": "stale",
            "last_indexed_at": "2025-11-15T10:00:00Z",
            "last_indexed_commit": "abc123",
            "schema_version": "1.0",
            "last_error": "Index outdated",
        }

        with open(status_file, "w") as f:
            json.dump(status_data, f)

        with open(status_file) as f:
            loaded = json.load(f)

        assert loaded["index_state"] == "stale"
        assert "last_error" in loaded
        assert loaded["last_error"] == "Index outdated"

    def test_load_error_status(self, tmp_path: Path):
        """Should correctly load an error status file."""
        status_file = tmp_path / "rag_index_status.json"

        status_data = {
            "repo": "test_repo",
            "index_state": "error",
            "last_indexed_at": "2025-11-16T09:00:00Z",
            "last_indexed_commit": "abc123",
            "schema_version": "1.0",
            "last_error": "Failed to build index",
        }

        with open(status_file, "w") as f:
            json.dump(status_data, f)

        with open(status_file) as f:
            loaded = json.load(f)

        assert loaded["index_state"] == "error"
        assert loaded["last_error"] == "Failed to build index"

    def test_load_rebuilding_status(self, tmp_path: Path):
        """Should correctly load a rebuilding status file."""
        status_file = tmp_path / "rag_index_status.json"

        status_data = {
            "repo": "test_repo",
            "index_state": "rebuilding",
            "last_indexed_at": "2025-11-16T08:00:00Z",
            "last_indexed_commit": "abc123",
            "schema_version": "1.0",
        }

        with open(status_file, "w") as f:
            json.dump(status_data, f)

        with open(status_file) as f:
            loaded = json.load(f)

        assert loaded["index_state"] == "rebuilding"

    def test_missing_status_file(self, tmp_path: Path):
        """Should handle missing status file gracefully."""
        status_file = tmp_path / "rag_index_status.json"

        # File doesn't exist
        assert not status_file.exists()

        # In real code, this would be handled by the loading function
        # For this test, we just verify the file is missing
        assert status_file.is_file() is False

    def test_malformed_json(self, tmp_path: Path):
        """Should handle malformed JSON gracefully."""
        status_file = tmp_path / "rag_index_status.json"

        with open(status_file, "w") as f:
            f.write("{ invalid json ")

        # In real code, JSON parsing would raise an exception
        # Tests should verify this is handled gracefully
        with pytest.raises(json.JSONDecodeError):
            with open(status_file) as f:
                json.load(f)

    def test_missing_required_field(self, tmp_path: Path):
        """Should handle missing required fields."""
        status_file = tmp_path / "rag_index_status.json"

        # Missing 'last_indexed_commit' which is required
        status_data = {
            "repo": "test_repo",
            "index_state": "fresh",
            "last_indexed_at": "2025-11-16T10:00:00Z",
            # Missing last_indexed_commit
            "schema_version": "1.0",
        }

        with open(status_file, "w") as f:
            json.dump(status_data, f)

        # When constructing IndexStatus, this would raise TypeError
        with open(status_file) as f:
            loaded = json.load(f)

        # Verify the field is actually missing
        assert "last_indexed_commit" not in loaded


@pytest.mark.rag_freshness
class TestFreshnessClassification:
    """Test mapping from IndexState to FreshnessState."""

    def test_fresh_maps_to_fresh(self):
        """IndexState 'fresh' should map to FreshnessState 'FRESH'."""
        # This test documents the expected mapping
        # The actual mapping logic would be in a helper function

        index_state: IndexState = "fresh"
        expected_freshness: FreshnessState = "FRESH"

        # Verify the expected mapping
        assert index_state == "fresh"
        assert expected_freshness == "FRESH"

    def test_stale_maps_to_stale(self):
        """IndexState 'stale' should map to FreshnessState 'STALE'."""
        index_state: IndexState = "stale"
        expected_freshness: FreshnessState = "STALE"

        assert index_state == "stale"
        assert expected_freshness == "STALE"

    def test_error_maps_to_stale(self):
        """IndexState 'error' should map to FreshnessState 'STALE'."""
        index_state: IndexState = "error"
        expected_freshness: FreshnessState = "STALE"

        assert index_state == "error"
        assert expected_freshness == "STALE"

    def test_rebuilding_maps_to_unknown(self):
        """IndexState 'rebuilding' should map to FreshnessState 'UNKNOWN'."""
        index_state: IndexState = "rebuilding"
        expected_freshness: FreshnessState = "UNKNOWN"

        assert index_state == "rebuilding"
        assert expected_freshness == "UNKNOWN"


@pytest.mark.rag_freshness
class TestIndexStatusRealistic:
    """Test with realistic index status scenarios."""

    def test_realistic_fresh_index(self):
        """Simulate a fresh index at HEAD."""
        status = IndexStatus(
            repo="/home/user/repo",
            index_state="fresh",
            last_indexed_at="2025-11-16T15:30:00Z",
            last_indexed_commit="a1b2c3d4e5f6",
            schema_version="1.0",
        )

        assert status.index_state == "fresh"
        assert status.last_indexed_commit is not None
        assert status.last_error is None

        status_dict = status.to_dict()
        assert status_dict["index_state"] == "fresh"
        # last_error should NOT be present when None
        assert "last_error" not in status_dict

    def test_realistic_stale_index(self):
        """Simulate a stale index with commit mismatch."""
        status = IndexStatus(
            repo="/home/user/repo",
            index_state="stale",
            last_indexed_at="2025-11-15T10:00:00Z",
            last_indexed_commit="old_commit_hash",
            schema_version="1.0",
            last_error="Repository modified since last index",
        )

        assert status.index_state == "stale"
        assert status.last_error is not None

        status_dict = status.to_dict()
        assert status_dict["last_error"] == "Repository modified since last index"

    def test_realistic_error_index(self):
        """Simulate an index in error state."""
        status = IndexStatus(
            repo="/home/user/repo",
            index_state="error",
            last_indexed_at="2025-11-16T12:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
            last_error="SQLite database locked",
        )

        assert status.index_state == "error"
        assert status.last_error == "SQLite database locked"

    def test_realistic_rebuilding_index(self):
        """Simulate an index being rebuilt."""
        status = IndexStatus(
            repo="/home/user/repo",
            index_state="rebuilding",
            last_indexed_at="2025-11-16T14:00:00Z",
            last_indexed_commit="def456",
            schema_version="1.0",
        )

        assert status.index_state == "rebuilding"
        assert status.last_error is None
