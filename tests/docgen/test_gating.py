"""
Tests for docgen gating logic (SHA256 and RAG freshness).
"""

import hashlib
from pathlib import Path

import pytest

from llmc.docgen.gating import (
    check_rag_freshness,
    compute_file_sha256,
    read_doc_sha256,
    resolve_doc_path,
    should_skip_sha_gate,
)


def test_compute_file_sha256(tmp_path):
    """Test SHA256 computation for files."""
    # Create test file
    test_file = tmp_path / "test.txt"
    test_content = b"Hello, World!"
    test_file.write_bytes(test_content)
    
    # Compute SHA
    sha = compute_file_sha256(test_file)
    
    # Verify it's a 64-char hex string
    assert len(sha) == 64
    assert all(c in "0123456789abcdef" for c in sha)
    
    # Verify it matches expected SHA256
    expected_sha = hashlib.sha256(test_content).hexdigest()
    assert sha == expected_sha


def test_compute_file_sha256_large_file(tmp_path):
    """Test SHA256 computation for large files (chunked reading)."""
    # Create large file (> 64KB)
    test_file = tmp_path / "large.bin"
    test_content = b"X" * (100 * 1024)  # 100KB
    test_file.write_bytes(test_content)
    
    # Compute SHA
    sha = compute_file_sha256(test_file)
    
    # Verify
    expected_sha = hashlib.sha256(test_content).hexdigest()
    assert sha == expected_sha


def test_compute_file_sha256_missing_file(tmp_path):
    """Test SHA256 computation for missing file raises error."""
    missing_file = tmp_path / "missing.txt"
    
    with pytest.raises(FileNotFoundError):
        compute_file_sha256(missing_file)


def test_read_doc_sha256_valid(tmp_path):
    """Test reading valid SHA256 header from doc."""
    doc_file = tmp_path / "doc.md"
    test_sha = "a" * 64
    doc_file.write_text(f"SHA256: {test_sha}\n\n# Documentation\n\nContent here")
    
    sha = read_doc_sha256(doc_file)
    assert sha == test_sha


def test_read_doc_sha256_missing_file(tmp_path):
    """Test reading SHA from missing file returns None."""
    missing_file = tmp_path / "missing.md"
    
    sha = read_doc_sha256(missing_file)
    assert sha is None


def test_read_doc_sha256_no_header(tmp_path):
    """Test reading SHA from doc without header returns None."""
    doc_file = tmp_path / "doc.md"
    doc_file.write_text("# Documentation\n\nNo SHA header")
    
    sha = read_doc_sha256(doc_file)
    assert sha is None


def test_read_doc_sha256_malformed_short(tmp_path):
    """Test reading malformed SHA (too short) returns None."""
    doc_file = tmp_path / "doc.md"
    doc_file.write_text("SHA256: abc123\n")
    
    sha = read_doc_sha256(doc_file)
    assert sha is None


def test_read_doc_sha256_malformed_non_hex(tmp_path):
    """Test reading malformed SHA (non-hex chars) returns None."""
    doc_file = tmp_path / "doc.md"
    bad_sha = "z" * 64  # 'z' is not a hex digit
    doc_file.write_text(f"SHA256: {bad_sha}\n")
    
    sha = read_doc_sha256(doc_file)
    assert sha is None


def test_should_skip_sha_gate_doc_missing(tmp_path):
    """Test skip logic when doc doesn't exist."""
    source_file = tmp_path / "source.py"
    source_file.write_text("print('hello')")
    
    doc_file = tmp_path / "doc.md"  # Doesn't exist
    
    should_skip, reason = should_skip_sha_gate(source_file, doc_file)
    
    assert should_skip is False
    assert reason == "Doc does not exist"


def test_should_skip_sha_gate_sha_match(tmp_path):
    """Test skip logic when SHA matches."""
    # Create source file
    source_file = tmp_path / "source.py"
    source_content = "print('hello')"
    source_file.write_text(source_content)
    
    # Compute SHA
    source_sha = hashlib.sha256(source_content.encode()).hexdigest()
    
    # Create doc with matching SHA
    doc_file = tmp_path / "doc.md"
    doc_file.write_text(f"SHA256: {source_sha}\n\n# Docs")
    
    should_skip, reason = should_skip_sha_gate(source_file, doc_file)
    
    assert should_skip is True
    assert "SHA256 match" in reason
    assert source_sha[:8] in reason


def test_should_skip_sha_gate_sha_mismatch(tmp_path):
    """Test skip logic when SHA doesn't match."""
    # Create source file
    source_file = tmp_path / "source.py"
    source_file.write_text("print('hello')")
    
    # Create doc with different SHA
    doc_file = tmp_path / "doc.md"
    old_sha = "b" * 64
    doc_file.write_text(f"SHA256: {old_sha}\n\n# Docs")
    
    should_skip, reason = should_skip_sha_gate(source_file, doc_file)
    
    assert should_skip is False
    assert "SHA256 mismatch" in reason


def test_should_skip_sha_gate_doc_no_header(tmp_path):
    """Test skip logic when doc exists but has no SHA header."""
    source_file = tmp_path / "source.py"
    source_file.write_text("print('hello')")
    
    doc_file = tmp_path / "doc.md"
    doc_file.write_text("# Docs with no SHA header")
    
    should_skip, reason = should_skip_sha_gate(source_file, doc_file)
    
    assert should_skip is False
    assert "missing valid SHA256 header" in reason


def test_resolve_doc_path():
    """Test resolving documentation path from source path."""
    repo_root = Path("/repo")
    relative_path = Path("tools/rag/database.py")
    
    doc_path = resolve_doc_path(repo_root, relative_path)
    
    expected = Path("/repo/DOCS/REPODOCS/tools/rag/database.py.md")
    assert doc_path == expected


def test_resolve_doc_path_custom_output_dir():
    """Test resolving doc path with custom output directory."""
    repo_root = Path("/repo")
    relative_path = Path("src/main.py")
    output_dir = "custom/docs"
    
    doc_path = resolve_doc_path(repo_root, relative_path, output_dir)
    
    expected = Path("/repo/custom/docs/src/main.py.md")
    assert doc_path == expected


def test_check_rag_freshness_not_indexed(tmp_path):
    """Test RAG freshness check when file not indexed."""
    # Create mock database
    from llmc.rag.database import Database
    
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Check freshness for file not in DB
    relative_path = Path("test.py")
    file_sha = "a" * 64
    
    is_fresh, reason = check_rag_freshness(db, relative_path, file_sha)
    
    assert is_fresh is False
    assert "SKIP_NOT_INDEXED" in reason


def test_check_rag_freshness_stale_index(tmp_path):
    """Test RAG freshness check when file indexed but SHA differs."""
    from llmc.rag.database import Database
    
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Insert file with old hash
    old_hash = "b" * 64
    db.conn.execute(
        "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
        ("test.py", "python", old_hash, 1000, 1234567890.0)
    )
    db.conn.commit()
    
    # Check freshness with new hash
    relative_path = Path("test.py")
    new_hash = "a" * 64
    
    is_fresh, reason = check_rag_freshness(db, relative_path, new_hash)
    
    assert is_fresh is False
    assert "SKIP_STALE_INDEX" in reason
    assert "hash mismatch" in reason


def test_check_rag_freshness_fresh(tmp_path):
    """Test RAG freshness check when file indexed and fresh."""
    from llmc.rag.database import Database
    
    db_path = tmp_path / "test.db"
    db = Database(db_path)
    
    # Insert file with matching hash
    file_hash = "a" * 64
    db.conn.execute(
        "INSERT INTO files (path, lang, file_hash, size, mtime) VALUES (?, ?, ?, ?, ?)",
        ("test.py", "python", file_hash, 1000, 1234567890.0)
    )
    db.conn.commit()
    
    # Check freshness
    relative_path = Path("test.py")
    
    is_fresh, reason = check_rag_freshness(db, relative_path, file_hash)
    
    assert is_fresh is True
    assert "RAG index fresh" in reason
