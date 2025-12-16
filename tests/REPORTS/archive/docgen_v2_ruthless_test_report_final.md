# Testing Report - Docgen V2 Ruthless Audit

## 1. Scope
- Repo / project: llmc
- Feature / change under test: Docgen V2 (feature/docgen-v2)
- Commit: 9617bf891cd6f9218ca5fca9285ac6fe55de2a37
- Date: 2025-12-03

## 2. Summary
- **Overall assessment:** **FAILURES FOUND**. While static analysis is clean and basic tests pass, severe stability and security issues exist.
- **Key risks:**
  - **High:** Remote Code Execution (RCE) via Path Traversal in configuration.
  - **Medium:** Application crash on corrupted/malformed RAG graph.
  - **Medium:** Resource leak (file descriptors) under high concurrency/timeouts.

## 3. Environment & Setup
- Environment: Linux, Python 3.12.3
- Dependencies: Installed.
- Setup: `mkdir -p tests/REPORTS`

## 4. Static Analysis
- **Ruff:** PASSED (0 issues)
- **Mypy:** PASSED (0 issues)
- **Note:** The code looks pretty, but pretty code can still be deadly.

## 5. Test Suite Results
- **Existing Tests:** 33 passed (tests/docgen) + 6 passed (tests/test_docgen_ren.py)
- **Ruthless Tests (New):**
  - `tests/test_docgen_ruthless_graph.py`: **PASSED** (Confirmed crash bug)
  - `tests/test_docgen_ruthless_lock.py`: **PASSED** (Confirmed FD leak bug)
  - `tests/test_docgen_ruthless_config.py`: **PASSED** (Confirmed path traversal)

## 6. Behavioral & Edge Testing

### Operation: Graph Context Building
- **Scenario:** Corrupted `rag_graph.json` (valid JSON list instead of dict).
- **Steps:** Create `.llmc/rag_graph.json` with content `[]`. Call `build_graph_context`.
- **Expected:** Graceful fallback or error message.
- **Actual:** `AttributeError: 'list' object has no attribute 'get'` (CRASH).
- **Status:** **FAIL**
- **Notes:** The dev fixed this in `load_graph_indices` (DD-003) but forgot the fallback path in `build_graph_context`.

### Operation: Concurrency Locking
- **Scenario:** Lock acquisition timeout.
- **Steps:** Simulate `BlockingIOError` on `flock` for longer than timeout.
- **Expected:** `RuntimeError` and file handle closed.
- **Actual:** `RuntimeError` but file handle LEAKED.
- **Status:** **FAIL**
- **Notes:** `return False` inside the timeout loop bypasses the `except` block that closes the handle.

### Operation: Backend Configuration
- **Scenario:** Path traversal in `script` path.
- **Steps:** Set `docs.docgen.shell.script = "../../../bin/sh"`.
- **Expected:** Error (script must be within repo).
- **Actual:** Script resolves to system path and executes.
- **Status:** **FAIL** (Security Vulnerability)
- **Notes:** Commit message admitted this ("path traversal... needed"), but now you have a weaponized test case proving it.

## 7. Documentation & DX Issues
- `design_decisions.md` claims DD-003 (Type Safety) is active, but the implementation is incomplete in `graph_context.py`.
- Security warnings in commit messages are accurate but understate the risk of RCE via config.

## 8. Most Important Bugs (Prioritized)

1. **Title:** Path Traversal / RCE in Shell Backend Config
   - **Severity:** Critical
   - **Area:** Security
   - **Repro:** `pytest tests/test_docgen_ruthless_config.py`
   - **Behavior:** Allows execution of arbitrary files outside the repo.
   - **Fix:** Validate `script_path` is relative to and contained within `repo_root`.

2. **Title:** Crash on Invalid Graph JSON Type
   - **Severity:** Medium
   - **Area:** Stability
   - **Repro:** `pytest tests/test_docgen_ruthless_graph.py`
   - **Behavior:** `AttributeError` crashing the process.
   - **Fix:** Apply the `isinstance(data, dict)` check to the fallback loading path in `build_graph_context`.

3. **Title:** File Descriptor Leak in Lock Timeout
   - **Severity:** Medium
   - **Area:** Resource Management
   - **Repro:** `pytest tests/test_docgen_ruthless_lock.py`
   - **Behavior:** `open()` handle remains open if `acquire()` returns `False` due to timeout.
   - **Fix:** Ensure `self._lock_handle.close()` is called before returning `False` in the timeout loop.

## 9. Coverage & Limitations
- Did not test `llm` or `http` backends as they are not implemented.
- Did not test large graph performance (relied on existing perf tests).
- Assumed `fcntl` availability (Linux only).

## 10. Ren's Vicious Remark
Oh, look at you, writing "Design Decisions" to excuse your type safety failures while leaving a gaping hole in the very next function. You fixed it in the batch loader because it was "slow," but left the single-file loader to crash and burn? Classic optimization-obsessed, stability-ignoring developer hubris. And don't get me started on the lock leak—you open a file, wait for it, give up, and just walk away leaving the door open? Were you raised in a barn? At least the RCE is consistent with your "move fast and break things" philosophy—specifically, breaking the user's security.