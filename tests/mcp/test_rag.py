#!/usr/bin/env python3
"""Unit tests for RAG adapter in LLMC MCP."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llmc_mcp.tools.rag import rag_bootload, rag_search


def test_rag_search_empty_query():
    """Test that empty query returns error."""
    print("Testing rag_search with empty query...")

    result = rag_search("", "/home/vmlinux/src/llmc")
    assert result.error is not None
    assert "required" in result.error.lower()

    print("  ✓ Empty query handled correctly")


def test_rag_search_valid_query():
    """Test that valid query returns results."""
    print("Testing rag_search with valid query...")

    result = rag_search(
        "MCP server configuration",
        "/home/vmlinux/src/llmc",
        limit=3,
    )

    assert result.error is None, f"Unexpected error: {result.error}"
    assert isinstance(result.snippets, list)
    assert len(result.snippets) > 0, "Expected at least one result"

    # Check snippet structure
    snippet = result.snippets[0]
    assert "rank" in snippet
    assert "path" in snippet
    assert "score" in snippet

    print(f"  ✓ Got {len(result.snippets)} results, top: {snippet['path']}")


def test_rag_search_result_format():
    """Test that result format matches expected schema."""
    print("Testing rag_search result format...")

    result = rag_search("search_spans", "/home/vmlinux/src/llmc", limit=1)

    if result.snippets:
        s = result.snippets[0]
        # Required fields per SDD
        assert "rank" in s, "Missing rank"
        assert "span_hash" in s, "Missing span_hash"
        assert "path" in s, "Missing path"
        assert "symbol" in s, "Missing symbol"
        assert "kind" in s, "Missing kind"
        assert "lines" in s, "Missing lines"
        assert "score" in s, "Missing score"
        assert isinstance(s["lines"], list) and len(s["lines"]) == 2

        print(f"  ✓ Result format valid: {s['symbol']} ({s['kind']})")
    else:
        print("  ⚠ No results to validate format")


def test_rag_bootload():
    """Test bootloader returns expected structure."""
    print("Testing rag_bootload...")

    result = rag_bootload("session-1", "task-1", "/home/vmlinux/src/llmc")

    assert "session_id" in result
    assert "task_id" in result
    assert "plan" in result
    assert "scope" in result
    assert result["session_id"] == "session-1"

    print(f"  ✓ Bootload response: scope={result['scope']}")


def main():
    """Run all RAG unit tests."""
    print("=" * 60)
    print("RAG Adapter Unit Tests (M2)")
    print("=" * 60)

    try:
        test_rag_search_empty_query()
        test_rag_search_valid_query()
        test_rag_search_result_format()
        test_rag_bootload()

        print("=" * 60)
        print("✓ All RAG unit tests passed!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
