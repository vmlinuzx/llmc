# Quick Security Audit: Docgen V2

**Date:** 2025-12-03  
**Scope:** `llmc/docgen/` module  
**Auditor:** Security-aware agent review

---

## ✅ Security Strengths Found

### 1. **No Shell Injection Vulnerabilities**
```python
# ✅ GOOD: shell=False (default)
subprocess.run(cmd, shell=False, ...)
```
**Status:** Safe - not using `shell=True`

### 2. **No Hardcoded Secrets**
- ✅ No API keys in source code
- ✅ No passwords hardcoded
- ✅ No tokens embedded

### 3. **No Code Injection**
- ✅ No `eval()` usage
- ✅ No `exec()` usage
- ✅ No dynamic code execution

### 4. **Path Validation Present**
```python
# llmc/docgen/backends/shell.py:177
if not script_path.exists():
    raise ValueError(f"Docgen script not found: {script_path}")
    
if not script_path.is_file():
    raise ValueError(f"Docgen script is not a file: {script_path}")
```
**Status:** Basic validation exists ✅

---

## ⚠️ Security Concerns Found

### 1. **Potential Path Traversal in File Operations**

**Risk Level:** MEDIUM  
**File:** `llmc/docgen/orchestrator.py`

```python
# Line 68-69: User-controlled relative_path
source_path = self.repo_root / relative_path  # ← What if relative_path = "../../etc/passwd"?
doc_path = resolve_doc_path(self.repo_root, relative_path, self.output_dir)

# Line 124: Opens file without validation
with open(source_path, encoding="utf-8") as f:
    source_contents = f.read()
```

**Attack Scenario:**
```python
orchestrator.process_file(Path("../../../../etc/passwd"))
# Could read arbitrary files on system!
```

**Mitigation Needed:**
```python
def validate_path_in_repo(repo_root: Path, relative_path: Path) -> Path:
    """Ensure path is within repo_root, prevent traversal."""
    full_path = (repo_root / relative_path).resolve()
    if not full_path.is_relative_to(repo_root):
        raise ValueError(f"Path traversal attempt: {relative_path}")
    return full_path
```

### 2. **No Resource Limits on File Reads**

**Risk Level:** MEDIUM  
**File:** `llmc/docgen/orchestrator.py`

```python
# Line 124-125: No size limit!
with open(source_path, encoding="utf-8") as f:
    source_contents = f.read()  # ← Can read 10GB file into memory!
```

**Attack Scenario:**
```python
# Attacker creates 10GB file
orchestrator.process_file(Path("huge_file.py"))
# ❌ OOM crash!
```

**Mitigation Needed:**
```python
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

file_size = source_path.stat().st_size
if file_size > MAX_FILE_SIZE:
    raise ValueError(f"File too large: {file_size} bytes")
```

### 3. **No Timeout on Graph Loading**

**Risk Level:** LOW  
**File:** `llmc/docgen/graph_context.py`

```python
# Line 50: No timeout on JSON parsing
with open(graph_index_path, encoding="utf-8") as f:
    graph_data = json.load(f)  # ← Could hang on malformed JSON
```

**Attack Scenario:**
- Maliciously crafted JSON with deep nesting
- Parser hangs indefinitely
- DoS attack

**Mitigation:** Consider using `orjson` with size limits or timeout wrappers

### 4. **Lock File Creation Without Permission Check**

**Risk Level:** LOW  
**File:** `llmc/docgen/locks.py`

```python
# Line 43: Creates lock file without checking permissions
self._lock_handle = open(self.lock_file, "w")
```

**Risk:** If run with elevated privileges, could create/overwrite files in sensitive locations

**Mitigation:** Validate lock file path is within expected directory

### 5. **Script Execution Without Signature Verification**

**Risk Level:** HIGH  
**File:** `llmc/docgen/backends/shell.py`

```python
# Line 67-73: Executes script from config without integrity check
result = subprocess.run(
    cmd,  # cmd = [script_path] + args
    input=input_json,
    ...
)
```

**Attack Scenario:**
1. Attacker compromises `llmc.toml`
2. Changes `docs.docgen.shell.script = "/path/to/malware.sh"`
3. Docgen executes arbitrary code

**Current Protection:** Path validation (must exist in repo)  
**Missing:** Signature verification, allowlist

**Mitigation:**
```python
# Option 1: Allowlist
ALLOWED_SCRIPTS = frozenset(["scripts/docgen.sh", "tools/gen_docs.py"])
if str(script_path.relative_to(repo_root)) not in ALLOWED_SCRIPTS:
    raise ValueError("Script not in allowlist")

# Option 2: Hash verification
SCRIPT_HASHES = {"scripts/docgen.sh": "abc123..."}
actual_hash = hashlib.sha256(script_path.read_bytes()).hexdigest()
if actual_hash != expected_hash:
    raise ValueError("Script integrity check failed")
```

---

## 🔴 Critical Missing Security Controls

### 1. **No Input Sanitization**
- User-provided paths not validated for traversal
- No allowlist of acceptable file patterns
- No size limits on inputs

### 2. **No Audit Logging**
- Who ran docgen?
- What files were processed?
- Any failures or suspicious activity?

### 3. **No Rate Limiting**
- Could be abused to DoS system
- No throttling on batch operations

### 4. **No Sandboxing**
- Shell scripts run with full process permissions
- No container/chroot isolation
- No resource limits (CPU, memory, disk)

---

## Security Test Cases Ren Should Run

```python
# Test 1: Path Traversal
def test_path_traversal_blocked():
    orchestrator = DocgenOrchestrator(...)
    with pytest.raises(ValueError):
        orchestrator.process_file(Path("../../../../etc/passwd"))

# Test 2: Resource Exhaustion
def test_huge_file_rejected():
    # Create 100MB file
    huge_file = tmp_path / "huge.py"
    huge_file.write_text("x" * (100 * 1024 * 1024))
    
    with pytest.raises(ValueError, match="too large"):
        orchestrator.process_file(Path("huge.py"))

# Test 3: Malicious Script Path
def test_malicious_script_blocked():
    config = {"docs": {"docgen": {
        "backend": "shell",
        "shell": {"script": "/usr/bin/curl"}  # Not a docgen script!
    }}}
    
    with pytest.raises(ValueError, match="not allowed"):
        load_shell_backend(repo_root, config["docs"]["docgen"])

# Test 4: Command Injection in Args
def test_command_injection_in_args():
    config = {"docs": {"docgen": {
        "backend": "shell",
        "shell": {
            "script": "scripts/docgen.sh",
            "args": ["; rm -rf /"]  # Injection attempt
        }
    }}}
    
    # Should be safe since shell=False, but test it anyway
    backend = load_shell_backend(repo_root, config["docs"]["docgen"])
    # Verify args are passed as separate list items, not concatenated
```

---

## Priority Fix Recommendations

### P0 (Critical - Fix Before Production)
1. ✅ **Add path traversal prevention**
2. ✅ **Add file size limits**
3. ✅ **Validate script paths against allowlist**

### P1 (High - Fix Soon)
4. Add audit logging for security events
5. Add resource limits (memory, CPU, timeout)
6. Add input validation for all user-controlled data

### P2 (Medium - Consider)
7. Add sandboxing for script execution
8. Add rate limiting
9. Add configuration signing/verification

---

## Conclusion

**Overall Security Posture:** MODERATE

✅ **Good:** No obvious code injection, shell injection, or hardcoded secrets  
⚠️ **Concerns:** Path traversal possible, no resource limits, weak script validation  
❌ **Missing:** Input sanitization, audit logging, sandboxing

**Recommendation:** Add the P0 fixes before using in production, especially if processing untrusted inputs.

---

## Would Current Ren Find These?

| Issue | Would Ren Catch It? | Why/Why Not |
|-------|-------------------|-------------|
| Path traversal | ❌ No | Doesn't test malicious paths |
| File size DoS | ❌ No | Only tests "large" not "malicious" |
| Script integrity | ❌ No | Doesn't verify security boundaries |
| Hardcoded secrets | ❌ No | Doesn't scan for patterns |
| Shell injection | ✅ Maybe | Might notice shell=True if present |

**Ren finds bugs, not vulnerabilities.** Different mindset needed.
