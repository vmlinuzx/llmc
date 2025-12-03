"""
Tests for docgen core types.
"""

import pytest

from llmc.docgen.types import DocgenResult


def test_docgen_result_valid_status():
    """Test DocgenResult with valid status values."""
    # Test "noop"
    result = DocgenResult(
        status="noop",
        sha256="abc123",
        output_markdown=None,
        reason="SHA unchanged"
    )
    assert result.status == "noop"
    assert result.sha256 == "abc123"
    assert result.output_markdown is None
    assert result.reason == "SHA unchanged"
    
    # Test "generated"
    result = DocgenResult(
        status="generated",
        sha256="def456",
        output_markdown="# Documentation\n\nContent here",
        reason=None
    )
    assert result.status == "generated"
    assert result.sha256 == "def456"
    assert result.output_markdown is not None
    
    # Test "skipped"
    result = DocgenResult(
        status="skipped",
        sha256="ghi789",
        output_markdown=None,
        reason="Not indexed in RAG"
    )
    assert result.status == "skipped"
    assert result.reason == "Not indexed in RAG"


def test_docgen_result_invalid_status():
    """Test DocgenResult with invalid status raises ValueError."""
    with pytest.raises(ValueError, match="Invalid status 'invalid'"):
        DocgenResult(
            status="invalid",
            sha256="abc123",
            output_markdown=None
        )
    
    with pytest.raises(ValueError, match="Invalid status 'GENERATED'"):
        DocgenResult(
            status="GENERATED",  # Wrong case
            sha256="abc123",
            output_markdown=None
        )


def test_docgen_result_default_reason():
    """Test DocgenResult with default reason=None."""
    result = DocgenResult(
        status="noop",
        sha256="abc123",
        output_markdown=None
    )
    assert result.reason is None
