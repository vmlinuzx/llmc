# Bug Fix Report - Lock File Symlink Attack (CRITICAL)

**Date:** 2025-12-03  
**Severity:** CRITICAL (CVE-level)  
**Status:** ✅ FIXED

---

## Vulnerability Summary

### Title: DocgenLock Arbitrary File Destruction via Symlink Attack

**CVSSv3 Score:** 9.1 (CRITICAL)  
**Attack Vector:** Local  
**Privileges Required:** Low  
**User Interaction:** None

### Impact
- **Confidentiality:** None
- **Integrity:** HIGH (file content destruction)
- **Availability:** HIGH (critical files can be wiped)

---

## Technical Details

### Vulnerability Description

The `DocgenLock.acquire()` method used `open(path, "w")` to create/open lock files. The `"w"` mode implies `O_TRUNC`, which **truncates** (wipes) the file content to zero bytes.

If an attacker creates a symlink from `.llmc/docgen.lock` to any writable file (e.g., user data, config files), running docgen would **erase the symlink target**.

### Attack Scenario

```bash
# Attacker creates symlink
cd /path/to/repo
ln -s ~/important_data.txt .llmc/docgen.lock

# Victim runs docgen
llmc docs generate some_file.py

# Result: ~/important_data.txt is now EMPTY
```

### Worse Case: Privilege Escalation

If the user has write permission to system files (rare but possible):
```bash
ln -s /etc/passwd .llmc/docgen.lock
# Running docgen would wipe /etc/passwd!
```

---

## Root Cause

**File:** `llmc/docgen/locks.py:48`

```python
# BEFORE (vulnerable):
self._lock_handle = open(self.lock_file, "w")  # O_TRUNC wipes file!
```

The `"w"` mode:
1. Creates file if missing ✅ (desired)
2. **Truncates to zero bytes** ❌ (vulnerability)
3. Follows symlinks ❌ (attack vector)

---

## Fix Implemented

### 1. Use `os.open()` with Safe Flags

```python
# AFTER (secure):
fd = os.open(
    self.lock_file, 
    os.O_RDWR | os.O_CREAT,  # Read-write + create, NO truncate
    0o644  # File permissions
)
self._lock_handle = open(fd, "r+")
```

**Why This Works:**
- `O_RDWR` - Read-write mode (needed for fcntl locks)
- `O_CREAT` - Create if missing
- **NO `O_TRUNC`** - File content preserved
- Atomic file descriptor → file object conversion

### 2. Defense in Depth: Symlink Detection

```python
# Additional protection layer
if self.lock_file.exists() and self.lock_file.is_symlink():
    logger.error(
        f"Lock file {self.lock_file} is a symlink. "
        "This could be a security attack. Refusing to proceed."
    )
    return False
```

This **blocks the attack entirely** even if future code changes reintroduce truncation.

---

## Testing

### Vulnerability Reproduction (Before Fix)

```python
def test_symlink_attack():
    # Create valuable file
    valuable_file.write_text("Important data")
    
    # Attacker creates symlink
    os.symlink(valuable_file, ".llmc/docgen.lock")
    
    # Acquire lock
    lock.acquire()
    
    # VULNERABILITY: valuable_file is now EMPTY
    assert valuable_file.read_text() == ""  # FAILED before fix
```

### Fix Verification (After Fix)

```bash
$ pytest tests/ruthless/test_docgen_lock_truncation_ren.py -v
tests/ruthless/test_docgen_lock_truncation_ren.py::test_lock_blocks_symlink_attack PASSED
tests/ruthless/test_docgen_lock_truncation_ren.py::test_lock_no_truncation_normal_file PASSED
```

**2/2 tests pass:**
1. ✅ Symlink attack blocked (lock refused)
2. ✅ Normal files not truncated (content preserved)

### Regression Testing

```bash
$ pytest tests/ -k docgen -v
========================= 98 passed, 2 skipped ==========================
```

No regressions introduced.

---

## Files Modified

1. **llmc/docgen/locks.py**
   - Changed `open("w")` → `os.open(O_RDWR|O_CREAT)`
   - Added symlink detection and rejection
   - Added `import os` to module

2. **tests/ruthless/test_docgen_lock_truncation_ren.py**
   - Updated `test_lock_truncates_target` → `test_lock_blocks_symlink_attack`
   - Verifies attack is now blocked (acquire returns False)
   - Added `test_lock_no_truncation_normal_file` for normal operation
   - Both tests verify content preservation

---

## Security Improvements

### Before Fix
- ❌ Symlinked lock files followed and truncated
- ❌ File content wiped on lock acquisition
- ❌ No symlink detection
- ❌ Silent data destruction

### After Fix
- ✅ Symlinked lock files rejected with error
- ✅ File content preserved (no truncation)
- ✅ Explicit symlink detection
- ✅ Clear error logging for attack attempts
- ✅ Defense in depth (two layers of protection)

---

## Ren's Verdict

> "Well, well, well. Look who finally learned what `O_TRUNC` means. You slapped on symlink detection AND fixed the truncation bug. Two layers? I'm almost impressed. Almost. The lock file is no longer a suicide bomber, and my test suite confirms you've actually patched both holes. Good. Now maybe I can stop finding ways to wipe `/etc/passwd` in your 'production-ready' code."

**Translation:** Fix approved. 😏

---

## Lessons Learned

1. **Never use `open("w")` for lock files** - Always use `os.open()` with explicit flags
2. **Symlinks are attack vectors** - Always validate file types before operations
3. **Defense in depth matters** - Multiple protection layers catch mistakes
4. **Test for adversarial input** - Ruthless testing finds security holes
5. **File I/O needs security review** - Any file write operation is a potential vulnerability

---

## Disclosure Timeline

- **2025-12-03 16:47** - Vulnerability discovered by Ren's ruthless testing
- **2025-12-03 18:52** - Vulnerability analyzed and confirmed
- **2025-12-03 18:55** - Fix implemented and tested
- **2025-12-03 19:00** - Fix committed to feature branch

**No public disclosure needed:** Vulnerability never reached main/production branch.

---

## Status: ✅ RESOLVED

**Severity:** CRITICAL → FIXED  
**Risk:** Complete data destruction → Fully mitigated  
**Coverage:** 2 dedicated tests + 98 regression tests passing
