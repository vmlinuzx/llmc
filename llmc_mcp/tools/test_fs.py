#!/usr/bin/env python3
"""Unit tests for filesystem security in LLMC MCP."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from llmc_mcp.tools.fs import (
    normalize_path,
    check_path_allowed,
    validate_path,
    read_file,
    list_dir,
    stat_path,
    PathSecurityError,
)


def test_normalize_path_basics():
    """Test basic path normalization."""
    print("Testing normalize_path basics...")
    
    # Absolute path stays absolute
    p = normalize_path("/home/test/file.txt")
    assert p.is_absolute()
    
    # .. gets resolved
    p = normalize_path("/home/test/../other/file.txt")
    assert ".." not in str(p)
    
    # ~ expands
    p = normalize_path("~/test.txt")
    assert "~" not in str(p)
    
    print("  ✓ Path normalization works")


def test_normalize_path_null_byte():
    """Test that null bytes are rejected."""
    print("Testing null byte rejection...")
    try:
        normalize_path("/home/test\x00/file.txt")
        assert False, "Should have raised PathSecurityError"
    except PathSecurityError as e:
        assert "null" in str(e).lower()
    print("  ✓ Null bytes rejected")


def test_check_path_allowed():
    """Test allowed roots checking."""
    print("Testing check_path_allowed...")
    
    allowed = ["/home/vmlinux/src/llmc"]
    
    # Inside allowed root
    assert check_path_allowed(Path("/home/vmlinux/src/llmc/file.txt"), allowed)
    assert check_path_allowed(Path("/home/vmlinux/src/llmc/sub/dir/file.txt"), allowed)
    
    # Outside allowed root
    assert not check_path_allowed(Path("/etc/passwd"), allowed)
    assert not check_path_allowed(Path("/home/vmlinux/other/file.txt"), allowed)
    
    # Empty allowed_roots = full access
    assert check_path_allowed(Path("/etc/passwd"), [])
    
    print("  ✓ Allowed roots checking works")


def test_validate_path_traversal():
    """Test that path traversal is blocked."""
    print("Testing traversal protection...")
    
    allowed = ["/home/vmlinux/src/llmc"]
    
    # Normal path inside allowed root works
    p = validate_path("/home/vmlinux/src/llmc/file.txt", allowed)
    assert p == Path("/home/vmlinux/src/llmc/file.txt")
    
    # Traversal attempt gets resolved and blocked
    try:
        validate_path("/home/vmlinux/src/llmc/../../../etc/passwd", allowed)
        assert False, "Should block traversal"
    except PathSecurityError as e:
        assert "outside" in str(e).lower()
    
    print("  ✓ Traversal protection works")


def test_read_file_missing():
    """Test read_file on non-existent file."""
    print("Testing read_file on missing file...")
    
    result = read_file("/home/vmlinux/src/llmc/nonexistent.txt", ["/home/vmlinux/src/llmc"])
    assert not result.success
    assert "not found" in result.error.lower()
    
    print("  ✓ Missing file handled correctly")


def test_list_dir_filters_hidden():
    """Test that hidden files are filtered by default."""
    print("Testing hidden file filtering...")
    
    result = list_dir("/home/vmlinux/src/llmc", ["/home/vmlinux/src/llmc"], include_hidden=False)
    assert result.success
    
    names = {e["name"] for e in result.data}
    assert ".git" not in names, "Hidden dirs should be filtered"
    
    # With include_hidden=True
    result2 = list_dir("/home/vmlinux/src/llmc", ["/home/vmlinux/src/llmc"], include_hidden=True)
    names2 = {e["name"] for e in result2.data}
    assert ".git" in names2, "Hidden dirs should be included with flag"
    
    print("  ✓ Hidden file filtering works")


def test_stat_returns_metadata():
    """Test stat returns proper metadata."""
    print("Testing stat metadata...")
    
    result = stat_path("/home/vmlinux/src/llmc/llmc.toml", ["/home/vmlinux/src/llmc"])
    assert result.success
    
    data = result.data
    assert data["type"] == "file"
    assert data["size"] > 0
    assert "mtime" in data
    assert "mode" in data
    
    print(f"  ✓ Stat returns: size={data['size']}, mode={data['mode']}")


def main():
    """Run all fs unit tests."""
    print("=" * 60)
    print("Filesystem Security Unit Tests")
    print("=" * 60)
    
    try:
        test_normalize_path_basics()
        test_normalize_path_null_byte()
        test_check_path_allowed()
        test_validate_path_traversal()
        test_read_file_missing()
        test_list_dir_filters_hidden()
        test_stat_returns_metadata()
        
        print("=" * 60)
        print("✓ All fs unit tests passed!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
