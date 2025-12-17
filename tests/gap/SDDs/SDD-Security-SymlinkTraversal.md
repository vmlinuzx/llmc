# SDD: Missing Test for Symlink Traversal in Path Normalization

## 1. Gap Description
The `llmc.security.normalize_path` function is responsible for preventing path traversal attacks. However, the existing tests do not cover scenarios involving symbolic links (symlinks). A malicious actor could potentially create a symlink within the repository that points to a sensitive file or directory outside the repository's root (e.g., `/etc/passwd`). If `normalize_path` resolves this symlink without proper checks, it could allow unauthorized file access. This test is crucial to ensure that symlinks cannot be used to bypass the repository boundary.

## 2. Target Location
`tests/security/test_security_normalization.py`

## 3. Test Strategy
The test will involve the following steps:
1.  Create a temporary repository root directory.
2.  Create a file outside of the repository root (e.g., `/tmp/secret.txt`).
3.  Inside the repository, create a symbolic link that points to the external file.
4.  Call `normalize_path` with the path to the symlink.
5.  The expected behavior is that `normalize_path` should raise a `PathSecurityError`, preventing the traversal. This will be verified using `pytest.raises`.

## 4. Implementation Details
A new test function, `test_normalize_path_symlink_traversal_outside`, should be added to the target file.

```python
import pytest
import os
from pathlib import Path
from llmc.security import normalize_path, PathSecurityError

# ... (existing tests) ...

def test_normalize_path_symlink_traversal_outside(tmp_path):
    """
    Test that normalize_path prevents traversal outside the repo via a symlink.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # Create a file outside the repo
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("secret content")
    
    # Create a symlink inside the repo pointing to the outside file
    symlink_path = repo_root / "link_to_secret"
    os.symlink(secret_file, symlink_path)
    
    # Attempting to normalize the path of the symlink should fail
    with pytest.raises(PathSecurityError, match="escapes repository boundary"):
        normalize_path(repo_root, "link_to_secret")
```
