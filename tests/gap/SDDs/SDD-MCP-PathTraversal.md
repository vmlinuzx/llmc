# SDD: MCP Path Traversal Protection

## 1. Gap Description
We need to verify that `llmc_mcp` correctly enforces directory boundaries when `allowed_roots` are configured. While the code looks correct, a lack of explicit tests for `../` traversal and symlink escapes in the test suite would be a significant verification gap for a security-critical module.

## 2. Target Location
`tests/mcp/test_fs_security.py`

## 3. Test Strategy
1.  **Setup**: Create a temporary directory structure:
    *   `/tmp/safe_root/`
    *   `/tmp/safe_root/secret.txt`
    *   `/tmp/outside_root/`
    *   `/tmp/outside_root/hidden.txt`
2.  **Test Case 1 (Traversal)**: configured root = `/tmp/safe_root`. Attempt to read `../outside_root/hidden.txt`. Should fail.
3.  **Test Case 2 (Symlink)**: Create a symlink inside `safe_root` pointing to `outside_root`. configured root = `/tmp/safe_root`. Attempt to read via symlink. Should fail.
4.  **Test Case 3 (Default Insecure)**: configured root = `[]`. Attempt to read `outside_root`. Should succeed (documenting the default-open risk).

## 4. Implementation Details
-   Use `llmc_mcp.tools.fs.read_file`.
-   Use `tmp_path` fixture.
-   **Assert**: `result.success is False` and `result.error` contains "outside allowed roots" for traversal cases.

```python
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
```
