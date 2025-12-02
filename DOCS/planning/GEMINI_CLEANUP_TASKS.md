# Gemini Cleanup Tasks - Code Quality Grinding

**Branch:** `feature/productization`  
**Date:** 2025-12-02  
**Source:** Roswaal ruthless test report (`tests/REPORTS/ruthless_test_report_dec02_2025.md`)

---

## Context

Claude (Antigravity) has fixed the **CRITICAL** and **HIGH** priority bugs from Roswaal's test report:
- ✅ BUG 1: Import error in `test_mcp_executables.py` - FIXED
- ✅ BUG 2: API key mismatch in `normalize_scores()` - FIXED

The remaining tasks are **MEDIUM** and **LOW** priority code quality issues that need grinding through. These are perfect for you to handle.

---

## Your Tasks

### 🟡 TASK 1: Fix Routing Test Expectations (MEDIUM)

**Files to fix:**
1. `tests/test_erp_routing.py::test_classify_query_keywords`
2. `tests/test_ruthless_edge_cases.py::test_classify_query_whitespace_only`

**Problem:** Tests expect different behavior than the code implements. Either the tests are stale or the code changed without updating tests.

**Details from Roswaal's report:**

**Test 1:** `test_erp_routing.py::test_classify_query_keywords`
```python
# Test expects:
assert res["route_name"] == "erp"

# Actual result:
{'route_name': 'code', 'confidence': 0.8, 'reasons': ['conflict-policy:prefer-code', 'code-keywords=for']}
```
**Root Cause:** Query "Check inventory for model number X100" contains "for" which triggers code detection. The conflict policy prefers code over ERP.

**Action:** Either update the test expectation OR adjust the routing policy. Investigate which is correct.

---

**Test 2:** `test_ruthless_edge_cases.py::test_classify_query_whitespace_only`
```python
# Test expects:
assert "default=docs" in result["reasons"]

# Actual:
result["reasons"] = ["empty-or-none-input"]
```
**Root Cause:** Code returns `"empty-or-none-input"` for whitespace-only queries, but test expects `"default=docs"`.

**Action:** Update test to expect `"empty-or-none-input"` in reasons, OR change the code to match the test if that's the correct behavior.

---

### 🟡 TASK 2: Run Ruff Auto-Fix (MEDIUM)

**Problem:** 2,020 linting errors, 1,434 are auto-fixable.

**Command:**
```bash
cd /home/vmlinux/src/llmc
ruff check --fix .
```

**Expected fixes:**
- ~1,000+ unsorted imports (I001)
- ~500+ deprecated typing (UP035: `List/Dict` → `list/dict`)
- ~100+ unused imports (F401)
- ~50+ f-strings without placeholders (F541)

**Action:**
1. Run `ruff check --fix .`
2. Review the changes (should be safe)
3. Commit with message: `"chore: Auto-fix 1,434 ruff linting errors"`

---

### 🟡 TASK 3: Run Ruff Format (MEDIUM)

**Problem:** 265+ files need formatting.

**Command:**
```bash
cd /home/vmlinux/src/llmc
ruff format .
```

**Action:**
1. Run `ruff format .`
2. Commit with message: `"chore: Format 265+ files with ruff"`

---

### 🟢 TASK 4: Add `llmc/__main__.py` (LOW - Optional)

**Problem:** `python3 -m llmc` doesn't work, must use `python3 -m llmc.main`

**Fix:** Create `llmc/__main__.py`:
```python
#!/usr/bin/env python3
"""Allow running llmc as: python3 -m llmc"""
from llmc.main import app

if __name__ == "__main__":
    app()
```

**Action:**
1. Create the file
2. Test: `python3 -m llmc --help`
3. Commit with message: `"feat: Add __main__.py for python3 -m llmc support"`

---

## Testing

After all fixes, run the test suite:

```bash
cd /home/vmlinux/src/llmc
pytest tests/ -v
```

**Expected results:**
- All tests should pass (or at least no new failures)
- Test collection should work without errors
- Linting errors should be reduced from 2,020 to ~586 (unfixable ones)

---

## Commit Strategy

Make **separate commits** for each task:

1. `fix: Update routing test expectations to match implementation`
2. `chore: Auto-fix 1,434 ruff linting errors`
3. `chore: Format 265+ files with ruff`
4. `feat: Add __main__.py for python3 -m llmc support` (optional)

---

## Success Criteria

- ✅ All routing tests pass
- ✅ Ruff linting errors reduced from 2,020 to <600
- ✅ All files properly formatted
- ✅ `python3 -m llmc --help` works (if Task 4 completed)
- ✅ No new test failures introduced

---

## Notes

- **Branch:** Work on `feature/productization` (already checked out)
- **Don't touch:** The critical/high priority fixes Claude already made
- **Be careful with:** Routing logic changes - understand the business logic before changing tests
- **Safe to auto-run:** `ruff check --fix` and `ruff format` are safe operations

---

## Reference

Full test report: `tests/REPORTS/ruthless_test_report_dec02_2025.md`

Roswaal's verdict: **Grade C+** - "Would not recommend deploying to production without significant cleanup."

Let's get this to an A! 💪
