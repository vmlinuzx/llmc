
# RUTHLESS TESTING REPORT - Routing Phase 4 (UPDATED)

Date: 2025-11-30
Tester: Ros (Margrave of the Border Territories)
Repo: /home/vmlinux/src/llmc (feature/phase3-query-routing)

## EXECUTIVE SUMMARY

**System Status: MULTIPLE CRITICAL FAILURES** ❌❌❌

Found **4 CRITICAL FAILURES** and several MEDIUM issues. The routing system has:
1. BROKEN test suite (import errors)
2. MISSING feature (tool_context override)
3. BUG in fenced code detection
4. MISSING debug info field

## CRITICAL FAILURES

### 1. BROKEN TEST SUITE - Import Errors
**Severity:** CRITICAL  
**Tests Affected:** `test_ruthless_edge_cases.py` (won't even load)
**Tests Affected:** ALL routing tests (7 failures found)

**Issue:** Test expects legacy symbol names that don't exist:
- `CODE_STRUCT_REGEX` → actual: `CODE_STRUCT_REGEXES`
- `ERP_SKU_REGEX` → actual: `ERP_SKU_RE`

**Evidence:**
```python
from llmc.routing.query_type import CODE_STRUCT_REGEX  # FAILS
```

**Impact:** 
- Cannot run test suite
- Backward compatibility completely broken
- Users relying on these symbols will crash

**Fix Required:** Add backward compatibility exports in `llmc/routing/query_type.py`:

```python
# Add at bottom of query_type.py
from .code_heuristics import (
    CODE_STRUCT_REGEXES as CODE_STRUCT_REGEX,  # legacy alias
    ERP_KEY_REGEX as ERP_SKU_REGEX,  # legacy alias (note: ERP_KEY_REGEX exists)
)
```

---

### 2. MISSING FEATURE - tool_context Override
**Severity:** CRITICAL  
**Tests Affected:** 3 tests fail (`test_classify_query_tool_context_code`, `test_classify_query_tool_context_erp` x2)

**Issue:** The `tool_context` parameter is ACCEPTED but NEVER USED.

The function signature:
```python
def classify_query(text: Optional[str], tool_context: Optional[Dict[str, Any]] = None)
```

But the parameter is never checked anywhere in the function body!

**Evidence:**
- Test: `classify_query("some random text", tool_context={"tool_id": "code_refactor"})`
- Expected: route="code", confidence=1.0
- Actual: route="erp", confidence=0.55 (detected "so" as ERP keyword)

**Impact:** Tool context forcing is completely non-functional

**Fix Required:** Add tool_context logic BEFORE heuristic scoring:

```python
# Add after normalization, before heuristic scoring
if tool_context and "tool_id" in tool_context:
    tool_id = tool_context["tool_id"].lower()
    if "code" in tool_id or "refactor" in tool_id or "analyze" in tool_id:
        return {
            "route_name": "code",
            "confidence": 1.0,
            "reasons": ["tool-context=code"]
        }
    elif "erp" in tool_id or "product" in tool_id or "lookup" in tool_id:
        return {
            "route_name": "erp",
            "confidence": 1.0,
            "reasons": ["tool-context=erp"]
        }
```

---

### 3. BUG - Fenced Code Detection Too Strict
**Severity:** CRITICAL  
**Tests Affected:** `test_classify_query_code_fences`

**Issue:** Fenced code regex requires newline BEFORE ```, rejecting valid queries.

Regex: `r'(^|
)```[\w-]*\s*
'`

**Failing Cases:**
- `"Here is the code: ```python
print('hi')
```"` ❌
- `"See code: ```js
console.log(1)
```"` ❌

**Working Cases:**
- `"```python
code
```"` ✅
- `"Here is the code:
```python
print('hi')
```"` ✅

**Impact:** Common query patterns ("Here's the code: ```") FAIL to detect fenced code

**Fix Required:** Change regex to allow non-newline characters before ```:

```python
# In code_heuristics.py, change FENCE_OPEN_RE from:
FENCE_OPEN_RE = re.compile(r'(^|
)```[\w-]*\s*
', re.MULTILINE)

# To:
FENCE_OPEN_RE = re.compile(r'(^|[\s:,\(\)\{\}\[\]])```[\w-]*\s*
', re.MULTILINE)
```

---

### 4. MISSING - target_index in Debug Info
**Severity:** CRITICAL  
**Tests Affected:** `test_query_routing_integration`

**Issue:** Integration test expects `debug_info["search"]["target_index"]` but field is MISSING.

**Evidence:**
```python
result.debug_info["search"]["target_index"] == "emb_code"  # KeyError!
```

Actual debug_info contains:
- rank
- score
- embedding_similarity
- routing
- multi_route_fanout

But NO `target_index`.

**Impact:** Integration tests fail, debugging routing decisions is harder

**Fix Required:** Add target_index to debug info in search_spans when routing is used

---

## TEST RESULTS SUMMARY

### Unit Tests
- `test_query_routing.py`: 4/6 PASS, 2/6 FAIL
  - ✅ test_classify_query_natural_language
  - ✅ test_classify_query_c_style
  - ❌ test_classify_query_code_snippet (minor: reason format)
  - ❌ test_classify_query_tool_context_code (CRITICAL: missing feature)
  - ❌ test_classify_query_tool_context_erp (CRITICAL: missing feature)
  - ❌ test_classify_query_code_fences (CRITICAL: regex bug)

- `test_erp_routing.py`: 3/6 PASS, 3/6 FAIL
  - ✅ test_classify_slice_erp_path
  - ✅ test_classify_slice_erp_content
  - ✅ test_config_mapping
  - ❌ test_classify_query_sku (minor: reason string)
  - ❌ test_classify_query_keywords (minor: reason string)
  - ❌ test_classify_query_tool_context (CRITICAL: missing feature)

### Integration Tests
- `test_query_routing_integration.py`: 0/1 PASS, 1/1 FAIL
  - ❌ test_query_routing_integration (CRITICAL: missing target_index)

### Edge Cases (Manual Testing)
- ✅ Very long queries (90k chars) - handled correctly
- ✅ Unicode characters - no crashes
- ✅ Malformed input (None, int, list, dict) - handled gracefully
- ✅ SQL injection attempts - no crashes
- ✅ Whitespace variations - handled correctly

---

## BEHAVIORAL ANALYSIS (WORKING CORRECTLY)

### Priority System
Priority is WORKING as designed:
1. Fenced Code (0.95) - Highest
2. Code Structure (0.85) 
3. Code Keywords (0.4 single, 0.8 double)
4. ERP SKU Pattern (0.85)
5. ERP Keywords (0.55 single, 0.70 double)
6. Default (docs)

**Evidence:**
- Fenced code + ERP → Code wins ✅
- Code structure + ERP → Code wins ✅
- Single code keyword vs single ERP keyword → ERP wins (0.55 > 0.4) ✅

### Conflict Resolution
Policy settings working:
- prefer_code_on_conflict = true (default)
- conflict_margin = 0.1 (default)

**Finding:** Score gaps usually > 0.1, so true conflicts are rare.

---

## RECOMMENDATIONS (PRIORITY ORDER)

### IMMEDIATE (Blockers)
1. **Fix import errors** - Add backward compatibility exports
2. **Implement tool_context override** - Critical missing feature
3. **Fix fenced code regex** - Breaking real user queries
4. **Add target_index to debug_info** - Integration tests depend on this

### HIGH (Important)
5. Update test expectations to match actual reason strings
6. Add comprehensive docstrings explaining scoring system
7. Add logging/observability tests

### MEDIUM (Nice to Have)
8. Consider raising single-code-keyword score from 0.4 to 0.5
9. Add TOML config override tests
10. Add more edge case tests

---

## MINIMAL FIX SET

To make tests pass, implement these 4 changes:

1. **query_type.py** - Add backward compatibility exports (5 lines)
2. **query_type.py** - Implement tool_context logic (15 lines)
3. **code_heuristics.py** - Fix fenced code regex (1 line)
4. **search.py** - Add target_index to debug_info (5 lines)

**Total: ~26 lines of code changes**

---

## TESTING LIMITATIONS

- Could not verify TOML config loading (Python version issues)
- Could not verify env var overrides (module reload issues)
- Logging/observability not tested
- Full test suite blocked by import errors

---

## CONCLUSION

The routing Phase 4 implementation has good architectural design but **4 critical failures** prevent it from working correctly. All failures are fixable with minimal code changes.

**Grade: D+** (Multiple critical bugs, but core logic is sound)

**Recommendation: DO NOT MERGE** until critical failures are fixed.

