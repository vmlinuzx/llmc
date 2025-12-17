"""
Test for search command regression.

This test prevents the P0 bug where search command used .file_path and .text
attributes that don't exist on SpanSearchResult.

Bug report: Roswaal P0 - 2025-12-02
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from llmc.commands.rag import search as search_command
from llmc.rag.search import SpanSearchResult


def test_search_command_uses_correct_attributes():
    """Verify search command uses correct SpanSearchResult attributes.

    Regression test for P0 bug where .file_path and .text were used
    instead of .path and .summary.
    """
    # Create mock results with correct attributes
    mock_results = [
        SpanSearchResult(
            span_hash="sha256:abc123",
            path=Path("test/file.py"),
            symbol="test_function",
            kind="function",
            start_line=10,
            end_line=20,
            score=0.95,
            summary="Test function for authentication",
            normalized_score=0.95,
            debug_info=None,
        ),
        SpanSearchResult(
            span_hash="sha256:def456",
            path=Path("src/auth.py"),
            symbol="validate_token",
            kind="function",
            start_line=50,
            end_line=75,
            score=0.88,
            summary="Validates JWT tokens",
            normalized_score=0.88,
            debug_info=None,
        ),
    ]

    # Mock the search function
    with patch("llmc.commands.rag.run_search_spans", return_value=mock_results):
        with patch("llmc.commands.rag.find_repo_root", return_value=Path("/mock/repo")):
            # Test text output - should not raise AttributeError
            with patch("typer.echo") as mock_echo:
                try:
                    search_command(query="test", limit=5, json_output=False)
                    # Verify echo was called (output was produced)
                    assert mock_echo.call_count > 0

                    # Check that .path was used (not .file_path)
                    calls = [str(call) for call in mock_echo.call_args_list]
                    # Should contain references to the paths
                    assert any("test/file.py" in str(call) for call in calls)
                    assert any("src/auth.py" in str(call) for call in calls)

                except AttributeError as e:
                    pytest.fail(f"Search command raised AttributeError: {e}")

            # Test JSON output - should not raise AttributeError
            with patch("typer.echo") as mock_echo:
                try:
                    search_command(query="test", limit=5, json_output=True)
                    assert mock_echo.call_count > 0

                    # Verify JSON output contains correct fields
                    import json

                    json_output = mock_echo.call_args[0][0]
                    data = json.loads(json_output)

                    # Should have results
                    assert len(data) == 2

                    # Check structure uses correct attribute names
                    assert "file" in data[0]
                    assert "symbol" in data[0]
                    assert "kind" in data[0]
                    assert "summary" in data[0]
                    assert "score" in data[0]

                    # Should NOT have wrong attribute names
                    assert "file_path" not in data[0]
                    assert "text" not in data[0]

                    # Verify actual values
                    assert data[0]["file"] == "test/file.py"
                    assert data[0]["symbol"] == "test_function"
                    assert data[0]["summary"] == "Test function for authentication"

                except AttributeError as e:
                    pytest.fail(
                        f"Search command JSON output raised AttributeError: {e}"
                    )


def test_span_search_result_attributes():
    """Verify SpanSearchResult has the expected attributes."""
    result = SpanSearchResult(
        span_hash="sha256:test",
        path=Path("test.py"),
        symbol="test_symbol",
        kind="function",
        start_line=1,
        end_line=10,
        score=0.9,
        summary="Test summary",
        normalized_score=0.9,
        debug_info={"test": "data"},
    )

    # Verify correct attributes exist
    assert hasattr(result, "path")
    assert hasattr(result, "symbol")
    assert hasattr(result, "kind")
    assert hasattr(result, "summary")
    assert hasattr(result, "score")
    assert hasattr(result, "start_line")
    assert hasattr(result, "end_line")

    # Verify incorrect attributes don't exist (the P0 bug)
    assert not hasattr(result, "file_path")
    assert not hasattr(result, "text")

    # Verify values
    assert result.path == Path("test.py")
    assert result.summary == "Test summary"
