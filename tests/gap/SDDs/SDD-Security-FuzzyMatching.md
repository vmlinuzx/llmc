# SDD: Missing Test for Complex/Nested Fuzzy Matching in Path Normalization

## 1. Gap Description
The `llmc.security.normalize_path` function includes a "fuzzy suffix match" feature to find files when an exact path is not provided. The current implementation sorts potential matches by path length. However, there are no explicit tests to verify this sorting behavior in complex scenarios, such as when multiple files with the same name exist at different directory depths. This could lead to unpredictable behavior where the function returns a less relevant file. This test will ensure that the fuzzy matching logic is robust, predictable, and well-documented.

## 2. Target Location
`tests/security/test_security_normalization.py`

## 3. Test Strategy
The test will create a temporary directory structure with multiple files having the same name but located at different nesting levels. It will then call `normalize_path` with just the filename and assert that the function returns the file with the shortest path, as the implementation currently intends.

## 4. Implementation Details
A new test function, `test_normalize_path_fuzzy_match_priority`, should be added to the target file.

```python
import pytest
from pathlib import Path
from llmc.security import normalize_path, PathSecurityError

# ... (existing tests) ...

def test_normalize_path_fuzzy_match_priority(tmp_path):
    """
    Test that fuzzy matching prioritizes shorter paths when multiple matches exist.
    """
    repo_root = tmp_path
    
    # Create two files with the same name at different depths
    (repo_root / "a" / "b" / "c").mkdir(parents=True)
    (repo_root / "a" / "b" / "c" / "target.py").write_text("deep content")
    
    (repo_root / "x").mkdir()
    (repo_root / "x" / "target.py").write_text("shallow content")
    
    # Fuzzy match for "target.py" should return the one with the shorter path
    result = normalize_path(repo_root, "target.py")
    
    assert result == Path("x/target.py")
```
