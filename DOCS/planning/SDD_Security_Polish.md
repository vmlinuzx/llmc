# SDD: Security Polish (Roadmap 1.3)

**Date:** 2025-12-19  
**Author:** Dave + Antigravity  
**Status:** Ready for Implementation  
**Priority:** P2 (Low-Medium Risk)  
**Effort:** 4-6 hours  
**Assignee:** Jules  

---

## 1. Executive Summary

Address two remaining P2 security issues from the 2025-12-17 audit:

| Priority | Issue | Location | Risk |
|----------|-------|----------|------|
| **P2** | `os.chdir()` in RAG tools | `llmc_mcp/tools/rag.py` | MEDIUM - race conditions |
| **P2** | Unvalidated `repo_root` in RAG | `llmc_mcp/tools/rag.py` | MEDIUM - no `allowed_roots` check |

**Full Report:** `tests/REPORTS/current/rem_mcp_2025-12-17.md`

---

## 2. Problem Statement

### Issue 1: `os.chdir()` Race Condition

**Location:** `llmc_mcp/tools/rag.py`

The RAG tools use `os.chdir(repo_root)` to change the working directory before operations. This is unsafe in a multi-threaded/async context because:

1. `os.chdir()` affects the entire process
2. Concurrent requests could interfere with each other
3. Relative paths become unpredictable

**Current Code Pattern (problematic):**
```python
def rag_search(repo_root: str, query: str):
    old_cwd = os.getcwd()
    os.chdir(repo_root)
    try:
        # ... search logic ...
    finally:
        os.chdir(old_cwd)
```

### Issue 2: Unvalidated `repo_root`

**Location:** `llmc_mcp/tools/rag.py`

The `repo_root` parameter is not validated against an allowlist. An attacker could potentially:

1. Point `repo_root` to arbitrary directories
2. Access files outside intended repositories
3. Bypass path traversal checks

---

## 3. Implementation Tasks

### Task 1: Remove `os.chdir()` Usage (2h)

**File:** `llmc_mcp/tools/rag.py`

Replace all `os.chdir()` calls with explicit path handling:

**Before:**
```python
def rag_search(repo_root: str, query: str):
    old_cwd = os.getcwd()
    os.chdir(repo_root)
    try:
        results = search_spans(query, limit=10)  # Uses cwd implicitly
    finally:
        os.chdir(old_cwd)
```

**After:**
```python
def rag_search(repo_root: str, query: str):
    repo_path = Path(repo_root).resolve()
    results = search_spans(query, limit=10, repo_root=repo_path)
```

**Steps:**
1. Grep for `os.chdir` in `llmc_mcp/`
2. For each occurrence, pass `repo_root` explicitly to called functions
3. Update called functions to accept `repo_root` parameter if needed
4. Remove `os.chdir()` and any `try/finally` restore patterns

**Acceptance Criteria:**
- [ ] No `os.chdir()` calls in `llmc_mcp/tools/rag.py`
- [ ] All functions use explicit path parameters
- [ ] Existing tests pass

---

### Task 2: Add `allowed_roots` Validation (2h)

**File:** `llmc_mcp/tools/rag.py`

Add validation to ensure `repo_root` is in the allowed list:

```python
from llmc.config import get_llmc_config

def validate_repo_root(repo_root: str) -> Path:
    """Validate repo_root is in allowed_roots.
    
    Raises:
        PermissionError: If repo_root is not allowed
    """
    config = get_llmc_config()
    allowed_roots = config.get("allowed_roots", [])
    
    # If no allowed_roots configured, allow any (backwards compat)
    if not allowed_roots:
        return Path(repo_root).resolve()
    
    repo_path = Path(repo_root).resolve()
    
    for allowed in allowed_roots:
        allowed_path = Path(allowed).resolve()
        try:
            repo_path.relative_to(allowed_path)
            return repo_path  # Valid - is under an allowed root
        except ValueError:
            continue
    
    raise PermissionError(f"repo_root '{repo_root}' is not under allowed_roots")
```

**Update all RAG tool entry points:**
```python
def rag_search(repo_root: str, query: str):
    repo_path = validate_repo_root(repo_root)  # Add this
    results = search_spans(query, limit=10, repo_root=repo_path)
```

**Add config example to `llmc.toml`:**
```toml
# Optional: Restrict RAG operations to specific directories
# If not set, any directory is allowed (backwards compatible)
allowed_roots = [
    "~/src",
    "/home/user/projects"
]
```

**Acceptance Criteria:**
- [ ] `validate_repo_root()` function exists
- [ ] All RAG tools call `validate_repo_root()` on entry
- [ ] Error message is clear when access is denied
- [ ] Backwards compatible when `allowed_roots` not configured

---

### Task 3: Add Security Tests (1h)

**File:** `tests/security/test_rag_security.py`

```python
import pytest
from pathlib import Path
from llmc_mcp.tools.rag import validate_repo_root

def test_repo_root_in_allowed_roots(tmp_path, monkeypatch):
    """Test valid repo_root passes validation."""
    allowed = str(tmp_path)
    monkeypatch.setenv("LLMC_ALLOWED_ROOTS", allowed)
    
    result = validate_repo_root(str(tmp_path / "myrepo"))
    assert result == tmp_path / "myrepo"

def test_repo_root_outside_allowed_roots(tmp_path, monkeypatch):
    """Test repo_root outside allowed_roots raises error."""
    allowed = str(tmp_path / "allowed")
    monkeypatch.setenv("LLMC_ALLOWED_ROOTS", allowed)
    
    with pytest.raises(PermissionError, match="not under allowed_roots"):
        validate_repo_root("/etc/passwd")

def test_repo_root_no_allowed_roots_configured():
    """Test backwards compatibility when no allowed_roots configured."""
    # Should not raise
    result = validate_repo_root("/any/path")
    assert result == Path("/any/path")

def test_no_chdir_in_rag_tools():
    """Ensure os.chdir is not used in RAG tools."""
    import ast
    from pathlib import Path
    
    rag_file = Path("llmc_mcp/tools/rag.py")
    tree = ast.parse(rag_file.read_text())
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if node.func.attr == "chdir":
                    pytest.fail("os.chdir() found in rag.py - should use explicit paths")
```

---

## 4. Testing

### Run Security Tests
```bash
pytest tests/security/test_rag_security.py -v
```

### Manual Validation
```bash
# Test that RAG still works after changes
mcgrep "router" --limit 5

# Verify no os.chdir in the file
grep -n "os.chdir" llmc_mcp/tools/rag.py
# Should return nothing
```

---

## 5. Success Criteria

- [ ] No `os.chdir()` calls in `llmc_mcp/tools/rag.py`
- [ ] `validate_repo_root()` function validates against `allowed_roots`
- [ ] All RAG tool entry points call validation
- [ ] Security tests pass
- [ ] Existing RAG functionality unaffected

---

## 6. Files Modified

| File | Change |
|------|--------|
| `llmc_mcp/tools/rag.py` | Remove `os.chdir`, add `validate_repo_root()` |
| `llmc/config.py` | Add `allowed_roots` config parsing (if needed) |
| `tests/security/test_rag_security.py` | New security tests |
| `llmc.toml.example` | Document `allowed_roots` option |

---

## 7. Notes for Jules

1. **Search first:** `grep -rn "os.chdir" llmc_mcp/` to find all occurrences
2. **Don't break existing tests:** Run `pytest tests/mcp/` after changes
3. **Backwards compatibility:** If `allowed_roots` is not set, allow any path
4. **Path resolution:** Always use `.resolve()` to handle symlinks and `..`
