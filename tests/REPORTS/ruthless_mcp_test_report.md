# 💀 RUTHLESS TESTING REPORT 💀
**MCP System M0-M4 Testing Sweep**

**Tester:** ROSWAAL L. TESTINGDOM, Margrave of the Border Territories 👑  
**Date:** 2025-12-01  
**System:** LLMC MCP Server (M0-M4 Complete per SDD)  
**Branch:** main (dirty state)

---

## 🎯 EXECUTIVE SUMMARY

**The system is NOT ready for production.** While 42 unit tests pass under ideal conditions, **critical barriers prevent normal execution**, and **API signatures don't match the SDD specification**.

**Severity:** 🔴 **CRITICAL**  
**Green tests are SUSPICIOUS** - they only pass under very specific, undocumented conditions.

---

## 📊 TEST RESULTS

### Unit Tests
- **Total:** 42 tests
- **Passed:** 42 (under perfect conditions)
- **Failed:** 0 (when properly configured)
- **Status:** ⚠️ MISLEADING - Tests only pass with specific setup

### Functional Tests
- **Config Loading:** ✅ PASS
- **Server Initialization:** ✅ PASS  
- **Health Check:** ✅ PASS
- **Tool Listing:** ✅ PASS
- **RAG Search:** 🔴 **FAIL** - API mismatch
- **File Operations:** 🔴 **FAIL** - API mismatch + functional failure

---

## 💥 CRITICAL FAILURES

### 1. 🔴 Test Execution Barriers (BLOCKER)

**Finding:** Tests **CANNOT** be run by anyone without deep system knowledge.

**Evidence:**
- ❌ **Missing `mcp` package** outside venv: `ModuleNotFoundError: No module named 'mcp.server'`
- ❌ **Missing pytest-asyncio**: Tests fail with "async def functions are not natively supported"
- ❌ **Wrong asyncio mode**: Tests require `--asyncio-mode=auto` flag
- ❌ **Wrong directory**: Tests fail if not run from repo root
- ❌ **Wrong python**: Uses `python` not `python3` in some environments

**Impact:** 
- New developers cannot run tests
- CI/CD likely broken unless specially configured
- This is a **complete blocker** for anyone trying to use the system

**Evidence:**
```bash
$ python -m pytest llmc_mcp/ -v
ModuleNotFoundError: No module named 'mcp.server'

$ python -m pytest llmc_mcp/test_smoke.py -v
async def functions are not natively supported
```

### 2. 🔴 API Signature Mismatch (CRITICAL)

**Finding:** The actual implementation **does not match the SDD specification**.

#### RAG Search
- **SDD Spec:** `rag_search(q, scope, k, budget_tokens) -> {snippets: [...], provenance: true}`
- **Actual Code:** `rag_search(query, repo_root, limit, scope, debug) -> RagSearchResult`
- **Status:** 🔴 **COMPLETE MISMATCH**

**Impact:**
- Clients cannot use the API as documented
- Anyone following the SDD will get `TypeError`
- This violates the fundamental contract

#### File Operations
- **SDD Spec:** `read_file(args: {path: str}) -> {data: str, meta: {...}}`
- **Actual Code:** `read_file(path, allowed_roots, max_bytes, encoding) -> FsResult`
- **Status:** 🔴 **COMPLETE MISMATCH**

**Impact:**
- SDD is useless for implementation
- API is non-intuitive and inconsistent

### 3. 🔴 Functional Failures (HIGH)

**Finding:** Even with correct signatures, core functionality fails.

#### RAG Search Returns Wrong Data
```python
# Expected (per SDD):
{"snippets": [{"text": "...", "src": "...", "score": 0.8}]}

# Actual:
RagSearchResult(snippets=[{"text": "...", "src": "...", "score": 0.8}])
```
**Error:** `KeyError: 'text'` when accessing `result.snippets[0]['text']`

#### File Read Fails
```python
result = read_file("/home/vmlinux/src/llmc/README.md", allowed_roots=["/home/vmlinux/src/llmc"])
# Returns: FsResult(success=False, data=None, meta={})
```
**Error:** File read returns `success=False` for a valid, readable file.

---

## 🕵️ ROOT CAUSE ANALYSIS

### Why Tests Pass (Misleading Green)
1. **Virtual environment isolation:** `mcp` package is installed in `.venv/`
2. **pytest-asyncio installed:** But not in pyproject.toml dependencies
3. **Correct flag passed:** `--asyncio-mode=auto` required but not documented
4. **Tests use internal APIs:** Unit tests bypass the MCP protocol layer

### Why System Appears "Green"
- Unit tests are isolated and use direct function calls
- They don't exercise the actual MCP protocol
- They don't test the public API
- They don't validate against the SDD spec

---

## 📋 DETAILED FINDINGS

### Environment Setup Issues
```
Issue: Missing dependency mcp.server
- User sees: ModuleNotFoundError
- Location: Outside .venv
- Fix: Add to pyproject.toml dependencies

Issue: Missing pytest-asyncio
- User sees: "async def functions are not natively supported"
- Location: Both inside and outside venv
- Fix: Add to pyproject.toml test dependencies

Issue: No asyncio mode configuration
- User sees: Tests fail despite pytest-asyncio installed
- Location: Requires --asyncio-mode=auto flag
- Fix: Configure in pyproject.toml or pytest.ini
```

### API Contract Violations

| Component | SDD Spec | Actual Implementation | Status |
|-----------|----------|----------------------|--------|
| rag_search params | q, scope, k, budget_tokens | query, repo_root, limit, scope, debug | 🔴 MISMATCH |
| rag_search return | dict with 'snippets' key | RagSearchResult object | 🔴 MISMATCH |
| read_file params | args dict with 'path' | path str, allowed_roots list | 🔴 MISMATCH |
| read_file return | dict with 'data' key | FsResult object | 🔴 MISMATCH |
| Tool execution | Direct API calls | Only through MCP protocol | 🔴 DIFFERENT |

### Functional Issues

**RAG Search:**
```python
# Test code
result = rag_search("config", scope="repo", k=2, budget_tokens=100)
# Error: TypeError: rag_search() got an unexpected keyword argument 'k'

# With correct params
result = rag_search(query="config", repo_root="/home/vmlinux/src/llmc", limit=2)
print(result.snippets[0]['text'])  # KeyError: 'text'
```

**File Read:**
```python
# Test code
result = read_file({"path": "/home/vmlinux/src/llmc/README.md"})
# Error: TypeError: read_file() missing 1 required positional argument

# With correct params
result = read_file("/home/vmlinux/src/llmc/README.md", ["/home/vmlinux/src/llmc"])
# Returns: FsResult(success=False, ...)
```

---

## 🎯 PRIORITY FIXES

### 🔥 Priority 1: Make Tests Executable (BLOCKER)
1. Add `mcp` to pyproject.toml dependencies
2. Add `pytest-asyncio` to pyproject.toml test dependencies
3. Configure asyncio mode in pyproject.toml:
   ```toml
   [tool.pytest.ini_options]
   asyncio_mode = "auto"
   ```
4. Document test execution in README

### 🔥 Priority 2: Fix API Signatures (CRITICAL)
Either:
**Option A:** Update code to match SDD
- Change `rag_search(query, repo_root, limit, scope, debug)` 
- To: `rag_search(q, scope, k, budget_tokens)`

**Option B:** Update SDD to match code
- Accept that implementation differs from spec
- Update SDD with correct signatures

**Recommendation:** Option A - keep SDD as the source of truth

### 🔥 Priority 3: Fix Functional Bugs (HIGH)
1. Fix RAG search to return proper dict structure
2. Fix file read to actually read files
3. Add integration tests that exercise the full MCP protocol

---

## 🧪 REPRODUCTION STEPS

### To See Test Barriers:
```bash
cd /home/vmlinux/src/llmc
python -m pytest llmc_mcp/ -v
# See: ModuleNotFoundError: No module named 'mcp.server'
```

### To See API Mismatch:
```bash
source /home/vmlinux/src/llmc/.venv/bin/activate
cd /home/vmlinux/src/llmc
python3 << 'EOF'
from llmc_mcp.tools.rag import rag_search
result = rag_search("config", scope="repo", k=2, budget_tokens=100)
# TypeError: rag_search() got an unexpected keyword argument 'k'
