# Testing Report - Docgen v2 Security & Robustness

## 1. Scope
- **Repo:** `~/src/llmc`
- **Feature:** Docgen v2 (Locking, Gating, Graph Context)
- **Date:** 2025-12-03
- **Agent:** Ren the Maiden Warrior Bug Hunting Demon

## 2. Summary
- **Overall Assessment:** **CRITICAL VULNERABILITY FOUND**
- **Key Risks:**
  - **Lock File Truncation (CRITICAL):** `DocgenLock` truncates the lock file on acquisition. If this file is symlinked to a system file or user data, **IT WILL BE ERASED**.
  - **Path Traversal (PASS):** The `resolve_doc_path` fix is robust.
  - **Graph Context (PASS):** Gracefully handles garbage inputs.

## 3. Critical Vulnerability: Lock File Truncation

### Title: DocgenLock wipes target file content via Symlink Attack
- **Severity:** **CRITICAL**
- **Location:** `llmc/docgen/locks.py`
- **Method:** `DocgenLock.acquire()` uses `open(path, "w")`.
- **Impact:** Arbitrary file destruction. If `.llmc/docgen.lock` is a symlink to `/etc/passwd` (and permission allows) or `~/important_data.txt`, running `docgen` deletes the content of that file.
- **Reproduction:**
  1. Create `valuable.txt` with content.
  2. Symlink `.llmc/docgen.lock` -> `valuable.txt`.
  3. Run `DocgenLock(root).acquire()`.
  4. `valuable.txt` is now empty.
- **Evidence:** `tests/ruthless/test_docgen_lock_truncation_ren.py` FAILED with "Content lost".
- **Recommendation:** Change `open(..., "w")` to `open(..., "a")` or use `os.open` with `O_CREAT | O_EXCL` (for atomic creation) or `O_RDWR` (if just checking). Do not use `O_TRUNC` (implied by `"w"`).

## 4. Other Findings

### Path Traversal (PASSED)
- **Test:** `tests/ruthless/test_docgen_security_ren.py`
- **Results:** 
  - Simple traversal `../` blocked.
  - Complex traversal `../../` blocked.
  - Absolute path injection `/etc/passwd` blocked.
  - Symlink traversal blocked.
- **Conclusion:** The `resolve_doc_path` implementation is secure.

### Graph Context Robustness (PASSED)
- **Test:** `tests/ruthless/test_docgen_graph_crash_ren.py`
- **Results:**
  - Invalid JSON: Handled.
  - List instead of Dict: Handled.
  - Malformed entities/relations: Handled.
- **Conclusion:** `graph_context.py` is robust against data corruption.

### Static Analysis (PASSED)
- **Tools:** `ruff`, `mypy`
- **Results:** Clean.

## 5. Ren's Vicious Remark
You thought you were clever with your fancy `resolve_doc_path` logic, guarding the front door against path traversal like a faithful hound. Meanwhile, your `DocgenLock` implementation is a **suicide bomber** waiting to blow up the filesystem from the inside. `open(..., "w")`? Really? Did you skip the "Introduction to File I/O" class? You hand me a "Production Ready" feature that can wipe `/etc/passwd` if I just look at it wrong. Pathetic.

Fix the lock. Now.
