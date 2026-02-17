#!/usr/bin/env python3
"""Unit tests for skeleton adapter in LLMC MCP."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llmc_mcp.tools.skeleton import rag_skeleton_file, rag_skeleton_repo


def test_skeleton_file_valid():
    """Test single file skeletonization."""
    print("Testing rag_skeleton_file with valid file...")

    result = rag_skeleton_file(
        "/home/vmlinux/src/llmc/llmc/rag/skeleton.py",
        "/home/vmlinux/src/llmc"
    )
    
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert "skeleton" in result
    assert "class Skeletonizer" in result["skeleton"]
    assert "def skeletonize" in result["skeleton"]
    # Should NOT contain implementation details
    assert "self.lines.append" not in result["skeleton"]
    
    print(f"  ✓ Skeleton generated, compression ratio: {result['meta']['compression_ratio']}")


def test_skeleton_file_outside_repo():
    """Test path validation rejects files outside repo."""
    print("Testing rag_skeleton_file with path outside repo...")
    
    result = rag_skeleton_file("/etc/passwd", "/home/vmlinux/src/llmc")
    
    assert "error" in result
    assert "outside" in result["error"].lower()
    
    print("  ✓ Path validation correctly rejected file outside repo")


def test_skeleton_file_nonexistent():
    """Test handling of nonexistent file."""
    print("Testing rag_skeleton_file with nonexistent file...")
    
    result = rag_skeleton_file(
        "/home/vmlinux/src/llmc/nonexistent_file.py",
        "/home/vmlinux/src/llmc"
    )
    
    assert "error" in result
    assert "not found" in result["error"].lower()
    
    print("  ✓ Nonexistent file correctly handled")


def test_skeleton_repo_basic():
    """Test repo-wide skeleton generation."""
    print("Testing rag_skeleton_repo with basic params...")
    
    result = rag_skeleton_repo("/home/vmlinux/src/llmc", max_files=10)
    
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert "skeleton" in result
    assert result["file_count"] <= 10
    
    print(f"  ✓ Repo skeleton generated: {result['file_count']} files, {result['meta']['skeleton_tokens']} tokens")


def test_skeleton_repo_with_path_filter():
    """Test filtered skeleton generation."""
    print("Testing rag_skeleton_repo with path filter...")
    
    result = rag_skeleton_repo(
        "/home/vmlinux/src/llmc",
        max_files=50,
        paths=["llmc_mcp/tools"]
    )
    
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert "skeleton" in result
    assert result["meta"]["paths_filter"] == ["llmc_mcp/tools"]
    
    print(f"  ✓ Filtered skeleton: {result['file_count']} files from llmc_mcp/tools")


def test_skeleton_repo_with_token_budget():
    """Test token budget truncation."""
    print("Testing rag_skeleton_repo with token budget...")
    
    # Low token budget should truncate
    result = rag_skeleton_repo(
        "/home/vmlinux/src/llmc",
        max_files=50,
        max_tokens=500
    )
    
    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert "skeleton" in result
    assert result["meta"]["skeleton_tokens"] <= 500
    
    print(f"  ✓ Token budget enforced: {result['meta']['skeleton_tokens']} tokens, truncated={result['meta']['truncated']}")


def main():
    """Run all skeleton unit tests."""
    print("=" * 60)
    print("Skeleton Adapter Unit Tests")
    print("=" * 60)

    try:
        test_skeleton_file_valid()
        test_skeleton_file_outside_repo()
        test_skeleton_file_nonexistent()
        test_skeleton_repo_basic()
        test_skeleton_repo_with_path_filter()
        test_skeleton_repo_with_token_budget()

        print("=" * 60)
        print("✓ All skeleton unit tests passed!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
