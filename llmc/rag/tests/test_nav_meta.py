"""
Unit tests for RagToolMeta and RagResult envelope structures.

These tests validate the shared result envelope used by RAG navigation tools,
ensuring stable JSON contracts and correct metadata handling.
"""

from dataclasses import dataclass
from typing import NamedTuple

import pytest

from llmc.rag.freshness import IndexStatus
from llmc.rag.nav_meta import (
    RagResult,
    RagToolMeta,
    error_result,
    fallback_result,
    ok_result,
)


@pytest.mark.rag_freshness
class TestRagToolMeta:
    """Test RagToolMeta dataclass behavior and defaults."""

    def test_default_values(self):
        """RagToolMeta should have correct default values."""
        meta = RagToolMeta()

        assert meta.status == "OK"
        assert meta.source == "RAG_GRAPH"
        assert meta.freshness_state == "UNKNOWN"
        assert meta.error_code is None
        assert meta.message is None
        assert meta.index_status is None

    def test_explicit_values(self):
        """RagToolMeta should accept explicit values for all fields."""
        index_status = IndexStatus(
            repo="test",
            index_state="fresh",
            last_indexed_at="2025-11-16T10:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
        )

        meta = RagToolMeta(
            status="FALLBACK",
            error_code="TEST_ERROR",
            message="Test message",
            source="LOCAL_FALLBACK",
            freshness_state="STALE",
            index_status=index_status,
        )

        assert meta.status == "FALLBACK"
        assert meta.error_code == "TEST_ERROR"
        assert meta.message == "Test message"
        assert meta.source == "LOCAL_FALLBACK"
        assert meta.freshness_state == "STALE"
        assert meta.index_status is index_status

    def test_to_dict_basic(self):
        """RagToolMeta.to_dict() should serialize all fields."""
        meta = RagToolMeta(
            status="ERROR",
            error_code="E123",
            message="Error message",
            source="NONE",
            freshness_state="STALE",
        )

        result = meta.to_dict()

        assert isinstance(result, dict)
        assert result["status"] == "ERROR"
        assert result["error_code"] == "E123"
        assert result["message"] == "Error message"
        assert result["source"] == "NONE"
        assert result["freshness_state"] == "STALE"
        assert "index_status" in result
        assert result["index_status"] is None

    def test_to_dict_with_index_status(self):
        """RagToolMeta.to_dict() should serialize IndexStatus if present."""
        index_status = IndexStatus(
            repo="test",
            index_state="fresh",
            last_indexed_at="2025-11-16T10:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
            last_error=None,
        )

        meta = RagToolMeta(
            status="OK",
            index_status=index_status,
        )

        result = meta.to_dict()

        assert "index_status" in result
        assert result["index_status"] is not None
        assert isinstance(result["index_status"], dict)
        assert result["index_status"]["repo"] == "test"
        assert result["index_status"]["index_state"] == "fresh"

    def test_to_dict_with_error(self):
        """RagToolMeta.to_dict() should include last_error when present."""
        index_status = IndexStatus(
            repo="test",
            index_state="error",
            last_indexed_at="2025-11-16T10:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
            last_error="Database connection failed",
        )

        meta = RagToolMeta(
            status="ERROR",
            index_status=index_status,
        )

        result = meta.to_dict()

        assert "index_status" in result
        assert "last_error" in result["index_status"]
        assert result["index_status"]["last_error"] == "Database connection failed"


@pytest.mark.rag_freshness
class TestRagResult:
    """Test RagResult generic envelope."""

    def test_empty_result(self):
        """RagResult with no items should work."""
        meta = RagToolMeta(status="OK")
        result = RagResult(meta=meta, items=())

        assert result.meta is meta
        assert result.items == ()

    def test_simple_items(self):
        """RagResult should handle simple string items."""
        items = ["item1", "item2", "item3"]
        meta = RagToolMeta(status="OK")
        result = RagResult(meta=meta, items=items)

        assert result.items == items

    def test_to_dict_simple_items(self):
        """RagResult.to_dict() should serialize simple items directly."""
        items = ["a", "b", "c"]
        meta = RagToolMeta(status="OK")
        result = RagResult(meta=meta, items=items)

        result_dict = result.to_dict()

        assert "meta" in result_dict
        assert "items" in result_dict
        assert result_dict["items"] == items
        assert isinstance(result_dict["items"], list)

    def test_to_dict_with_to_dict_method(self):
        """RagResult should use item.to_dict() if available."""

        @dataclass
        class CustomItem:
            value: str

            def to_dict(self):
                return {"custom_value": self.value}

        items = [CustomItem("test1"), CustomItem("test2")]
        meta = RagToolMeta(status="OK")
        result = RagResult(meta=meta, items=items)

        result_dict = result.to_dict()

        assert len(result_dict["items"]) == 2
        assert result_dict["items"][0] == {"custom_value": "test1"}
        assert result_dict["items"][1] == {"custom_value": "test2"}

    def test_to_dict_with_asdict(self):
        """RagResult should use item._asdict() for namedtuples."""

        class CustomNamedTuple(NamedTuple):
            field1: str
            field2: int

        items = [CustomNamedTuple("a", 1), CustomNamedTuple("b", 2)]
        meta = RagToolMeta(status="OK")
        result = RagResult(meta=meta, items=items)

        result_dict = result.to_dict()

        assert len(result_dict["items"]) == 2
        assert result_dict["items"][0] == {"field1": "a", "field2": 1}
        assert result_dict["items"][1] == {"field1": "b", "field2": 2}

    def test_to_dict_with_mixed_types(self):
        """RagResult should handle mixed item types correctly."""

        @dataclass
        class CustomItem:
            value: str

            def to_dict(self):
                return {"custom": self.value}

        items = [
            "simple_string",
            42,
            CustomItem("custom"),
        ]
        meta = RagToolMeta(status="OK")
        result = RagResult(meta=meta, items=items)

        result_dict = result.to_dict()

        assert result_dict["items"][0] == "simple_string"
        assert result_dict["items"][1] == 42
        assert result_dict["items"][2] == {"custom": "custom"}

    def test_empty_items_serialization(self):
        """RagResult with empty items should serialize correctly."""
        meta = RagToolMeta(status="ERROR", error_code="NO_ITEMS")
        result = RagResult(meta=meta, items=[])

        result_dict = result.to_dict()

        assert "items" in result_dict
        assert result_dict["items"] == []
        assert isinstance(result_dict["items"], list)


@pytest.mark.rag_freshness
class TestOkResult:
    """Test ok_result helper constructor."""

    def test_ok_result_defaults(self):
        """ok_result should set correct defaults."""
        items = ["a", "b"]
        result = ok_result(items)

        assert result.meta.status == "OK"
        assert result.meta.source == "RAG_GRAPH"
        assert result.meta.freshness_state == "FRESH"
        assert result.items == items
        assert result.meta.error_code is None
        assert result.meta.message is None

    def test_ok_result_custom_source(self):
        """ok_result should accept custom source."""
        items = ["x"]
        result = ok_result(items, source="CUSTOM_SOURCE")

        assert result.meta.source == "CUSTOM_SOURCE"

    def test_ok_result_custom_freshness(self):
        """ok_result should accept custom freshness_state."""
        items = ["y"]
        result = ok_result(items, freshness_state="STALE")

        assert result.meta.freshness_state == "STALE"

    def test_ok_result_with_index_status(self):
        """ok_result should accept and attach IndexStatus."""
        index_status = IndexStatus(
            repo="test",
            index_state="fresh",
            last_indexed_at="2025-11-16T10:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
        )

        items = ["z"]
        result = ok_result(items, index_status=index_status)

        assert result.meta.index_status is index_status

    def test_ok_result_with_message(self):
        """ok_result should accept optional message."""
        items = ["msg"]
        result = ok_result(items, message="All good")

        assert result.meta.message == "All good"

    def test_ok_result_empty_items(self):
        """ok_result should handle empty items list."""
        result = ok_result([])

        assert result.items == []
        assert result.meta.status == "OK"


@pytest.mark.rag_freshness
class TestFallbackResult:
    """Test fallback_result helper constructor."""

    def test_fallback_result_defaults(self):
        """fallback_result should set correct defaults."""
        items = ["a", "b"]
        result = fallback_result(items)

        assert result.meta.status == "FALLBACK"
        assert result.meta.source == "LOCAL_FALLBACK"
        assert result.meta.freshness_state == "STALE"
        assert result.items == items

    def test_fallback_result_custom_freshness(self):
        """fallback_result should accept custom freshness_state."""
        items = ["x"]
        result = fallback_result(items, freshness_state="UNKNOWN")

        assert result.meta.freshness_state == "UNKNOWN"

    def test_fallback_result_with_index_status(self):
        """fallback_result should accept and attach IndexStatus."""
        index_status = IndexStatus(
            repo="test",
            index_state="stale",
            last_indexed_at="2025-11-16T10:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
        )

        items = ["y"]
        result = fallback_result(items, index_status=index_status)

        assert result.meta.index_status is index_status

    def test_fallback_result_with_message(self):
        """fallback_result should accept optional message."""
        items = ["z"]
        result = fallback_result(items, message="Using local fallback")

        assert result.meta.message == "Using local fallback"

    def test_fallback_result_empty_items(self):
        """fallback_result should handle empty items list."""
        result = fallback_result([])

        assert result.items == []
        assert result.meta.status == "FALLBACK"


@pytest.mark.rag_freshness
class TestErrorResult:
    """Test error_result helper constructor."""

    def test_error_result_required_fields(self):
        """error_result should require error_code and message."""
        result = error_result(error_code="E123", message="Test error")

        assert result.meta.status == "ERROR"
        assert result.meta.source == "NONE"
        assert result.meta.freshness_state == "UNKNOWN"
        assert result.meta.error_code == "E123"
        assert result.meta.message == "Test error"
        assert result.items == ()

    def test_error_result_default_freshness(self):
        """error_result should default freshness_state to UNKNOWN."""
        result = error_result(error_code="E001", message="Error")

        assert result.meta.freshness_state == "UNKNOWN"

    def test_error_result_custom_freshness(self):
        """error_result should accept custom freshness_state."""
        result = error_result(
            error_code="E001",
            message="Error",
            freshness_state="STALE",
        )

        assert result.meta.freshness_state == "STALE"

    def test_error_result_with_index_status(self):
        """error_result should accept and attach IndexStatus."""
        index_status = IndexStatus(
            repo="test",
            index_state="error",
            last_indexed_at="2025-11-16T10:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
        )

        result = error_result(
            error_code="E001",
            message="Error",
            index_status=index_status,
        )

        assert result.meta.index_status is index_status

    def test_error_result_serialization(self):
        """error_result should serialize error_code and message correctly."""
        result = error_result(error_code="DB_CONNECTION_FAILED", message="Cannot connect")

        result_dict = result.to_dict()

        assert "meta" in result_dict
        assert result_dict["meta"]["status"] == "ERROR"
        assert result_dict["meta"]["error_code"] == "DB_CONNECTION_FAILED"
        assert result_dict["meta"]["message"] == "Cannot connect"
        assert result_dict["items"] == []


@pytest.mark.rag_freshness
class TestRoundTripSerialization:
    """Test that serialization round-trips correctly."""

    def test_meta_round_trip(self):
        """Meta should survive dict->object->dict round trip."""
        index_status = IndexStatus(
            repo="test_repo",
            index_state="fresh",
            last_indexed_at="2025-11-16T10:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
            last_error=None,
        )

        original_meta = RagToolMeta(
            status="OK",
            error_code=None,
            message="Success",
            source="RAG_GRAPH",
            freshness_state="FRESH",
            index_status=index_status,
        )

        meta_dict = original_meta.to_dict()

        # Verify all expected keys are present
        assert "status" in meta_dict
        assert "error_code" in meta_dict
        assert "message" in meta_dict
        assert "source" in meta_dict
        assert "freshness_state" in meta_dict
        assert "index_status" in meta_dict

    def test_result_round_trip(self):
        """RagResult should survive dict->object->dict round trip."""
        items = ["a", "b", "c"]
        original = RagResult(
            meta=RagToolMeta(status="OK", freshness_state="FRESH"),
            items=items,
        )

        result_dict = original.to_dict()

        assert "meta" in result_dict
        assert "items" in result_dict
        assert result_dict["items"] == items
        assert result_dict["meta"]["status"] == "OK"
