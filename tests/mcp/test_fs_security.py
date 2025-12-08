import os
import pytest
from pathlib import Path
from llmc_mcp.tools.fs import read_file

def test_path_traversal_prevention(tmp_path):
    # Setup
    safe_root = tmp_path / "safe"
    safe_root.mkdir()
    (safe_root / "ok.txt").write_text("ok")
    
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    
    # 1. Direct Traversal
    # Try to access ../outside/secret.txt relative to safe_root
    # Note: read_file takes an absolute path or relative to CWD. 
    # We simulate a "user" request.
    
    # If we pass absolute path to secret, it should be blocked if allowed_roots is [safe_root]
    result = read_file(str(outside / "secret.txt"), allowed_roots=[str(safe_root)])
    assert result.success is False
    assert "outside allowed roots" in result.error

def test_symlink_escape_prevention(tmp_path):
    safe_root = tmp_path / "safe"
    safe_root.mkdir()
    
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "target.txt"
    target.write_text("target")
    
    # Symlink inside safe pointing out
    link = safe_root / "link_out"
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("Symlinks not supported")
        
    result = read_file(str(link), allowed_roots=[str(safe_root)])
    assert result.success is False
    assert "Symlink escapes" in result.error

def test_default_is_full_access(tmp_path):
    # Gap documentation: verifying that empty roots = unsafe
    p = tmp_path / "test.txt"
    p.write_text("data")
    
    result = read_file(str(p), allowed_roots=[])
    assert result.success is True
