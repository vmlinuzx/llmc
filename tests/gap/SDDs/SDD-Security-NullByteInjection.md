# SDD: Missing Test for Null Byte Injection in Path Normalization

## 1. Gap Description
The `llmc.security.normalize_path` function contains a check to prevent null bytes in paths, but no corresponding test exists to validate this security control. A null byte (`\x00`) can cause file path truncation in lower-level C functions, potentially leading to security bypasses where a malicious user could gain access to unintended files. This test is essential to ensure the null byte check is effective and not accidentally removed in future refactoring.

## 2. Target Location
`tests/security/test_security_normalization.py`

## 3. Test Strategy
The test will call `normalize_path` with a path string containing a null byte. The expected outcome is that a `PathSecurityError` is raised. This will be implemented using `pytest.raises`.

## 4. Implementation Details
A new test function, `test_normalize_path_null_byte_injection`, should be added to the target file.

```python
import pytest
from pathlib import Path
from llmc.security import normalize_path, PathSecurityError

# ... (existing tests) ...

def test_normalize_path_null_byte_injection(tmp_path):
    """
    Test that normalize_path rejects paths containing null bytes.
    """
    repo_root = tmp_path
    malicious_path = "safe/path\x00/../../etc/passwd"
    
    with pytest.raises(PathSecurityError, match="Path contains null bytes"):
        normalize_path(repo_root, malicious_path)

```
