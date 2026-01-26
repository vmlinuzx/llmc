# RLM Phase 1.1.1 Bug Fixes - Implementation Plan

**Branch:** feature/rlm-phase-1.1.1  
**Priority:** P0  
**Total Effort:** 2-3 hours  
**Acceptance Criteria:** All 17/17 tests passing, ready to merge to main

---

## Task List

### Bug #1: TreeSitterNav Symbol Extraction
- [x] ✅ ALREADY FIXED - No action needed
  - Test `test_ls_filters_by_scope` is passing
  - Recursion into class bodies working correctly
  - Roadmap entry was stale

### Bug #2: urllib3 Dependency Conflict (CRITICAL)
- [ ] **Task 2.1:** Analyze urllib3 usage in codebase
  - **Parallelizable:** NO (must complete before 2.2)
  - Grep for `import urllib3` and `from urllib3` across llmc/
  - Identify if any code requires urllib3 >= 2.6.0 specifically
  - Check if downgrading to 2.3.x would break anything

- [ ] **Task 2.2:** Fix pyproject.toml urllib3 constraint
  - **Parallelizable:** NO (depends on 2.1)
  - Change line 12 from `urllib3>=2.6.0` to `urllib3>=1.24.2,<2.4.0`
  - This satisfies both kubernetes (via chromadb) and security requirements
  - Alternative: Consider removing chromadb if unused (ROADMAP 2.12 suggests it's dead weight)

- [ ] **Task 2.3:** Verify installation in clean venv
  - **Parallelizable:** NO (depends on 2.2)
  - Create fresh venv
  - Run `pip install -e .[agent]`
  - Confirm litellm installs without conflict
  - Confirm urllib3 version satisfies all dependencies

### Bug #3: DeepSeek Integration Testing
- [ ] **Task 3.1:** Verify litellm installation
  - **Parallelizable:** NO (depends on 2.3)
  - Confirm `import litellm` works
  - Check litellm version compatibility with DeepSeek API

- [ ] **Task 3.2:** Set up DeepSeek API key
  - **Parallelizable:** YES (with 3.1)
  - Obtain API key from deepseek.com (if not already available)
  - Export `DEEPSEEK_API_KEY=sk-xxxxx` in environment
  - Verify key is valid with simple API call

- [ ] **Task 3.3:** Run integration test - Basic functionality
  - **Parallelizable:** NO (depends on 3.1, 3.2)
  - Run `pytest tests/rlm/test_integration_deepseek.py::test_rlm_deepseek_code_analysis -v -s`
  - Expected: Session completes successfully
  - Expected: FINAL() answer extracted
  - Expected: Budget tracking shows total_cost_usd <= $0.10
  - If fails: Debug litellm response format issues

- [ ] **Task 3.4:** Run integration test - Budget enforcement
  - **Parallelizable:** NO (depends on 3.3)
  - Run `pytest tests/rlm/test_integration_deepseek.py::test_rlm_deepseek_budget_enforcement -v -s`
  - Expected: Session stops when budget exceeded
  - Expected: No overspend beyond 10% grace margin
  - If fails: Debug budget accounting logic

- [ ] **Task 3.5:** Verify all tests pass
  - **Parallelizable:** NO (depends on 3.4)
  - Run full RLM test suite: `pytest tests/rlm/ -v`
  - Expected: 43/43 tests passing (no skipped)
  - If fails: Fix any regressions

### Final Verification
- [ ] **Task 4.1:** Run full project test suite
  - **Parallelizable:** NO (final gate)
  - Run `pytest tests/` to catch any cross-module issues
  - Confirm no new failures introduced

- [ ] **Task 4.2:** Update ROADMAP.md
  - **Parallelizable:** YES (with 4.1)
  - Mark section 1.Y as ✅ COMPLETE
  - Add completion date
  - Document any deviations from original plan

---

## Research Context (from explore agent)

### Key Findings:
1. **Bug #1 is a false alarm** - Test already passing, roadmap stale
2. **Bug #2 is the critical blocker** - urllib3 2.6.0 incompatible with kubernetes (required by chromadb)
3. **Bug #3 cannot be tested** until Bug #2 is fixed (litellm won't install)

### Files to Modify:
- `pyproject.toml` - Fix urllib3 constraint (line 12)
- `DOCS/ROADMAP.md` - Update completion status (line 826-881)

### Files to Read/Verify:
- `llmc/rlm/session.py` - Session loop using litellm
- `tests/rlm/test_integration_deepseek.py` - Integration test expectations
- `llmc/rlm/governance/pricing.json` - DeepSeek pricing config

### Critical Path:
1. Fix urllib3 (15 min)
2. Install litellm (5 min)
3. Run DeepSeek tests (1-2 hrs including debugging)

---

## Implementation Guidance

### For Task 2.2 (urllib3 fix):
**Reference pattern in pyproject.toml:**
```toml
# Current (line 12):
dependencies = ["urllib3>=2.6.0", ...]

# Change to:
dependencies = ["urllib3>=1.24.2,<2.4.0", ...]
```

**Rationale:**
- kubernetes 34.1.0 requires `urllib3<2.4.0,>=1.24.2`
- Current constraint `>=2.6.0` conflicts with kubernetes
- New constraint satisfies both (security minimum + kubernetes maximum)

### For Task 3.3 & 3.4 (DeepSeek tests):
**Watch for these litellm API quirks:**
1. Response format: `response.usage.prompt_tokens` and `response.usage.completion_tokens`
2. Message extraction: `response.choices[0].message.content`
3. DeepSeek model name format: `"deepseek/deepseek-chat"`

**Debugging tips:**
- If API format mismatches, check litellm docs for DeepSeek provider
- If budget tracking fails, verify pricing.json has correct DeepSeek rates
- If FINAL() extraction fails, check sandbox execution output format

---

## Success Criteria

- ✅ All 43/43 RLM tests passing (0 skipped)
- ✅ DeepSeek integration test completes successfully
- ✅ Budget tracking accurate (within 5% of expected)
- ✅ No urllib3 dependency conflicts
- ✅ Clean `pip install -e .[agent]` in fresh venv
- ✅ Ready to merge to main

---

## Notes

**From research agent:**
- Current branch appears to be `feat/rlm-config-nested-phase-1x`, not `feature/rlm-phase-1.1.1`
- May need to create correct branch or work on existing one
- 41/43 tests currently passing (2 skipped due to missing litellm)
