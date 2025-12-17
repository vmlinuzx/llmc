"""
Integration tests for RAG navigation tools and envelope contracts.

These tests verify that RAG navigation tools correctly use RagResult envelopes
and maintain stable JSON contracts for MCP and CLI output.

NOTE: The navigation tools are not yet integrated with RagResult envelopes.
These tests serve as:
1. Documentation of expected integration behavior
2. A test scaffold ready for implementation
3. Contract validation tests
"""

import json
from pathlib import Path

import pytest

from llmc.rag.freshness import IndexStatus
from llmc.rag.nav_meta import RagResult, RagToolMeta


@pytest.mark.rag_freshness
class TestToolEnvelopeContract:
    """
    Test that all RAG nav tools return properly structured RagResult envelopes.
    """

    def test_simple_result_structure(self):
        """
        A simple result should have the expected envelope structure.

        This test creates a RagResult directly (until real tools are integrated).
        """
        items = ["result1", "result2", "result3"]
        meta = RagToolMeta(
            status="OK",
            source="RAG_GRAPH",
            freshness_state="FRESH",
        )
        result = RagResult(meta=meta, items=items)

        result_dict = result.to_dict()

        # Verify top-level structure
        assert "meta" in result_dict
        assert "items" in result_dict

        # Verify meta structure
        assert isinstance(result_dict["meta"], dict)
        assert result_dict["meta"]["status"] == "OK"
        assert result_dict["meta"]["source"] == "RAG_GRAPH"
        assert result_dict["meta"]["freshness_state"] == "FRESH"

        # Verify items structure
        assert isinstance(result_dict["items"], list)
        assert len(result_dict["items"]) == 3

    def test_fallback_result_structure(self):
        """
        A fallback result should have the expected envelope structure.
        """
        items = ["fallback1", "fallback2"]
        meta = RagToolMeta(
            status="FALLBACK",
            source="LOCAL_FALLBACK",
            freshness_state="STALE",
        )
        result = RagResult(meta=meta, items=items)

        result_dict = result.to_dict()

        assert result_dict["meta"]["status"] == "FALLBACK"
        assert result_dict["meta"]["source"] == "LOCAL_FALLBACK"
        assert result_dict["meta"]["freshness_state"] == "STALE"
        assert len(result_dict["items"]) == 2

    def test_error_result_structure(self):
        """
        An error result should have the expected envelope structure.
        """
        meta = RagToolMeta(
            status="ERROR",
            error_code="RAG_UNAVAILABLE",
            message="RAG index is not available",
            source="NONE",
            freshness_state="UNKNOWN",
        )
        result = RagResult(meta=meta, items=[])

        result_dict = result.to_dict()

        assert result_dict["meta"]["status"] == "ERROR"
        assert result_dict["meta"]["error_code"] == "RAG_UNAVAILABLE"
        assert result_dict["meta"]["message"] == "RAG index is not available"
        assert result_dict["meta"]["source"] == "NONE"
        assert result_dict["meta"]["freshness_state"] == "UNKNOWN"
        assert result_dict["items"] == []

    def test_result_with_index_status(self):
        """
        A result with IndexStatus should serialize correctly.
        """
        index_status = IndexStatus(
            repo="test_repo",
            index_state="fresh",
            last_indexed_at="2025-11-16T15:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
        )

        items = ["item1"]
        result = RagResult(
            meta=RagToolMeta(
                status="OK",
                freshness_state="FRESH",
                index_status=index_status,
            ),
            items=items,
        )

        result_dict = result.to_dict()

        assert "index_status" in result_dict["meta"]
        assert result_dict["meta"]["index_status"]["repo"] == "test_repo"
        assert result_dict["meta"]["index_status"]["index_state"] == "fresh"
        assert result_dict["meta"]["index_status"]["last_indexed_commit"] == "abc123"


@pytest.mark.rag_freshness
class TestJsonContract:
    """
    Test that the JSON contract is stable and well-formed.

    This ensures MCP clients and other callers can rely on a stable schema.
    """

    def test_meta_has_all_required_fields(self):
        """
        The meta dictionary should always contain these fields.
        """
        meta = RagToolMeta()
        meta_dict = meta.to_dict()

        required_fields = [
            "status",
            "error_code",
            "message",
            "source",
            "freshness_state",
            "index_status",
        ]

        for field in required_fields:
            assert field in meta_dict, f"Missing required field: {field}"

    def test_error_code_only_present_when_error(self):
        """
        error_code should be None for non-error statuses.
        """
        # OK status
        meta_ok = RagToolMeta(status="OK")
        assert meta_ok.error_code is None

        # FALLBACK status
        meta_fallback = RagToolMeta(status="FALLBACK")
        assert meta_fallback.error_code is None

        # ERROR status
        meta_error = RagToolMeta(status="ERROR", error_code="TEST_ERROR")
        assert meta_error.error_code == "TEST_ERROR"

    def test_message_optional_for_all_statuses(self):
        """
        message can be present or absent for any status.
        """
        # No message
        meta1 = RagToolMeta(status="OK")
        assert meta1.message is None

        # With message
        meta2 = RagToolMeta(status="OK", message="All good")
        assert meta2.message == "All good"

    def test_status_values_are_literal(self):
        """
        status must be one of the defined literal values.
        """
        meta = RagToolMeta()

        # These should all be valid
        for status in ["OK", "FALLBACK", "ERROR"]:
            meta.status = status
            assert meta.status in ["OK", "FALLBACK", "ERROR"]

    def test_source_values_are_literal(self):
        """
        source must be one of the defined literal values.
        """
        meta = RagToolMeta()

        # These should all be valid
        for source in ["RAG_GRAPH", "LOCAL_FALLBACK", "NONE"]:
            meta.source = source
            assert meta.source in ["RAG_GRAPH", "LOCAL_FALLBACK", "NONE"]

    def test_freshness_state_values_are_literal(self):
        """
        freshness_state must be one of the defined literal values.
        """
        meta = RagToolMeta()

        # These should all be valid
        for freshness in ["FRESH", "STALE", "UNKNOWN"]:
            meta.freshness_state = freshness
            assert meta.freshness_state in ["FRESH", "STALE", "UNKNOWN"]

    def test_index_status_optional(self):
        """
        index_status can be None or an IndexStatus object.
        """
        # None
        meta1 = RagToolMeta()
        assert meta1.index_status is None

        # IndexStatus object
        index_status = IndexStatus(
            repo="test",
            index_state="fresh",
            last_indexed_at="2025-11-16T15:00:00Z",
            last_indexed_commit="abc123",
            schema_version="1.0",
        )
        meta2 = RagToolMeta(index_status=index_status)
        assert meta2.index_status is index_status


@pytest.mark.rag_freshness
class TestToolIntegrationScenarios:
    """
    Test realistic scenarios of tool integration.

    These simulate how the navigation tools would use the envelope system.
    """

    @pytest.mark.skip(reason="Navigation tools not yet integrated with RagResult")
    def test_search_tool_with_fresh_index(self, tmp_path: Path):
        """
        Search tool with fresh index should return OK with RAG_GRAPH source.
        """
        # Setup a fixture repo with fresh index
        repo_dir = tmp_path / "fixture_repo"
        repo_dir.mkdir()

        # Create some files
        (repo_dir / "file1.py").write_text("def function_a(): pass")
        (repo_dir / "file2.py").write_text("def function_b(): pass")

        # Create a fresh index status
        status_file = repo_dir / ".llmc" / "rag_index_status.json"
        status_file.parent.mkdir()
        status_file.write_text(
            json.dumps(
                {
                    "repo": str(repo_dir),
                    "index_state": "fresh",
                    "last_indexed_at": "2025-11-16T15:00:00Z",
                    "last_indexed_commit": "abc123",
                    "schema_version": "1.0",
                }
            )
        )

        # Mock or call the actual search tool
        # result = search_tool(repo_dir, "function_a")

        # assert isinstance(result, RagResult)
        # assert result.meta.status == "OK"
        # assert result.meta.source == "RAG_GRAPH"
        # assert result.meta.freshness_state == "FRESH"
        pass

    @pytest.mark.skip(reason="Navigation tools not yet integrated with RagResult")
    def test_where_used_with_stale_index(self, tmp_path: Path):
        """
        Where-used tool with stale index should return FALLBACK.
        """
        # Setup a fixture repo with stale index
        repo_dir = tmp_path / "fixture_repo"
        repo_dir.mkdir()

        status_file = repo_dir / ".llmc" / "rag_index_status.json"
        status_file.parent.mkdir()
        status_file.write_text(
            json.dumps(
                {
                    "repo": str(repo_dir),
                    "index_state": "stale",
                    "last_indexed_at": "2025-11-15T10:00:00Z",
                    "last_indexed_commit": "old123",
                    "schema_version": "1.0",
                }
            )
        )

        # Mock or call the actual where-used tool
        # result = where_used_tool(repo_dir, "function_a")

        # assert result.meta.status == "FALLBACK"
        # assert result.meta.source == "LOCAL_FALLBACK"
        # assert result.meta.freshness_state == "STALE"
        pass

    @pytest.mark.skip(reason="Navigation tools not yet integrated with RagResult")
    def test_lineage_tool_without_index(self, tmp_path: Path):
        """
        Lineage tool without index should return ERROR.
        """
        # Setup a repo without index
        repo_dir = tmp_path / "fixture_repo"
        repo_dir.mkdir()

        # No .llmc directory

        # Mock or call the actual lineage tool
        # result = lineage_tool(repo_dir, "ClassA")

        # assert result.meta.status == "ERROR"
        # assert result.meta.error_code == "RAG_UNAVAILABLE"
        # assert result.meta.source == "NONE"
        # assert result.items == []
        pass


@pytest.mark.rag_freshness
class TestCliOutput:
    """
    Test CLI output contracts (when CLI tools are implemented).

    This ensures that command-line tools produce stable JSON output.
    """

    @pytest.mark.skip(reason="CLI integration not yet implemented")
    def test_cli_json_output_structure(self, tmp_path: Path):
        """
        CLI tools should output valid JSON with correct structure.
        """
        # This would test running a CLI tool with --json flag
        # cmd = ["python", "-m", "llmc.rag.cli", "search", "query", "--json"]
        # result = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)

        # assert result.returncode == 0

        # Parse JSON output
        # output = json.loads(result.stdout)

        # Verify structure
        # assert "meta" in output
        # assert "items" in output
        pass

    @pytest.mark.skip(reason="CLI integration not yet implemented")
    def test_cli_error_output(self, tmp_path: Path):
        """
        CLI tools should output error results as JSON when --json is used.
        """
        # Test that errors are also in the RagResult envelope
        pass


@pytest.mark.rag_freshness
class TestMcpContract:
    """
    Test MCP (Model Context Protocol) output contracts.

    This ensures that MCP-compatible tools produce the expected structure.
    """

    def test_mcp_compatible_structure(self):
        """
        The result structure should be compatible with MCP expectations.

        MCP typically expects:
        - A content field
        - Metadata field
        - Or a content array with items
        """
        # Our RagResult.to_dict() structure should be MCP-compatible
        items = ["result1", "result2"]
        result = RagResult(
            meta=RagToolMeta(status="OK"),
            items=items,
        )

        result_dict = result.to_dict()

        # Verify it has the basic structure MCP expects
        assert isinstance(result_dict, dict)
        assert "meta" in result_dict
        assert "items" in result_dict
        assert isinstance(result_dict["items"], list)

    def test_error_has_structured_metadata(self):
        """
        Error results should have enough metadata for MCP error handling.
        """
        result = RagResult(
            meta=RagToolMeta(
                status="ERROR",
                error_code="SEARCH_FAILED",
                message="Search query invalid",
            ),
            items=[],
        )

        result_dict = result.to_dict()

        # Verify error information is structured
        assert result_dict["meta"]["status"] == "ERROR"
        assert "error_code" in result_dict["meta"]
        assert "message" in result_dict["meta"]
        assert result_dict["items"] == []


@pytest.mark.rag_freshness
class TestContractBackwardCompatibility:
    """
    Test that the contract remains backward compatible.

    This ensures changes don't break existing callers.
    """

    def test_adding_optional_fields_preserves_compatibility(self):
        """
        Adding optional fields to meta shouldn't break existing code.
        """
        # Create a result
        result = RagResult(
            meta=RagToolMeta(status="OK"),
            items=["item1"],
        )

        # Convert to dict
        result_dict = result.to_dict()

        # Add a new optional field (simulating a future addition)
        result_dict["meta"]["new_optional_field"] = "value"

        # Existing code should still be able to access old fields
        assert result_dict["meta"]["status"] == "OK"
        assert result_dict["items"] == ["item1"]

    def test_required_fields_never_removed(self):
        """
        Required fields should never be removed from the contract.
        """
        meta = RagToolMeta()
        meta_dict = meta.to_dict()

        # These are the current required fields - they should always be present
        required_fields = [
            "status",
            "error_code",
            "message",
            "source",
            "freshness_state",
            "index_status",
        ]

        for field in required_fields:
            assert field in meta_dict, f"Required field '{field}' was removed from meta contract"

    def test_status_literal_values_stable(self):
        """
        The literal values for status should remain stable.
        """
        # These are the current valid status values
        valid_statuses = ["OK", "FALLBACK", "ERROR"]

        # Verify they are all documented and stable
        for status in valid_statuses:
            meta = RagToolMeta(status=status)
            assert meta.status in valid_statuses
