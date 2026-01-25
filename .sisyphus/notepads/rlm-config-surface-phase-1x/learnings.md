# Learnings Log

## Session: ses_4098cfd94ffeXX20t5vamQeOrA

### Agent Delegation Issues
**Problem**: All 3 delegation attempts resulted in agents modifying files outside scope
- Asked for inventory → got implementation
- Asked for RED tests → got GREEN implementation  
- Asked for inventory recovery → got same implementation again

**Root Cause**: Prompts may have been too permissive, or agents have context from previous sessions leading them to "complete the work"

**Mitigation**: Switched to direct tool calls for documentation tasks

### Implementation Discoveries

**Config Structure** (`llmc/rlm/config.py`):
- RLMConfig dataclass expanded from ~10 fields to 29 fields
- Fields organized logically but still flat (not nested dataclasses yet)
- `validate()` method added for basic validation
- `load_rlm_config()` partially implemented but incomplete

**Parsing Logic** (`_parse_rlm_section`):
- Uses `dataclasses.replace()` for merging overrides
- Has error handling for unknown fields
- Sandbox sub-section partially handled
- **MISSING**: Nested section parsing (budget, llm.root, llm.sub, etc.)
- **MISSING**: Legacy alias support
- **MISSING**: Deprecation warnings
- **MISSING**: Precedence rules

**Test Coverage**:
- Original 7 tests still pass
- Fixture TOMLs created but not utilized by tests yet
- No tests for nested parsing (Task 2 not actually done)

### What's Actually Complete
✅ Task 0: Baseline captured
✅ Task 1: Inventory created (manually)
⚠️ Task 2: Partially done (config expanded, but no RED tests for NESTED parsing)
⚠️ Task 3: Partially done (basic parsing works, nested sections NOT implemented)
❌ Task 4: Not done (nested config structures/views not added)
❌ Task 5: Not done (wiring not updated)
❌ Task 6: Not done (CLI not updated)
❌ Task 7: Not done (no documentation)
❌ Task 8: Not done (final verification pending)

### Critical Gaps
1. **Nested section parsing**: load_rlm_config doesn't actually parse [rlm.budget], [rlm.llm.root], etc.
2. **Deprecation warnings**: No DeprecationWarning system implemented
3. **Alias handling**: max_tokens_per_session → max_session_tokens not handled
4. **Nested config views**: No BudgetConfig, SandboxConfig, LLMConfig dataclasses
5. **Wiring**: session.py, sandbox, etc. not updated to use config

### Next Steps
Focus on completing the core missing pieces:
1. Implement ACTUAL nested parsing in load_rlm_config
2. Add nested config view dataclasses
3. Wire through critical paths (budget, sandbox)
4. Add tests
5. Documentation

## Recovery Actions Taken

### Selective Revert
Reverted chaotic changes:
- ❌ llmc.toml bloat (948 lines → 8 lines) - was completely unrelated config
- ❌ Unrelated files (service.py, AGENTS.md, pyproject.toml, plans)

Kept useful changes:
- ✅ llmc/rlm/config.py (expanded RLMConfig, basic parsing)
- ✅ llmc/rlm/session.py (uses config fields)
- ✅ llmc/rlm/governance/budget.py (load_pricing update)
- ✅ llmc/rlm/sandbox/* (accepts config params)
- ✅ llmc/rlm/nav/treesitter_nav.py (accepts config)
- ✅ tests/fixtures/rlm_config_*.toml (good test data)
- ✅ DOCS/reference/config/rlm.md (documentation started)

### Test Status After Cleanup
All tests pass: 7/7 in test_config.py, full RLM suite passes (14 tests, 2 skipped)

### Revised Task Status
✅ Task 0: Baseline captured
✅ Task 1: Inventory created (manually)
⚠️ Task 2: Partial - need to add tests for nested parsing
⚠️ Task 3: Partial - basic parsing works, NESTED sections not implemented
❌ Task 4: Nested config views not added
⚠️ Task 5: Partial wiring done
❌ Task 6: CLI not updated
⚠️ Task 7: Partial docs exist
❌ Task 8: Final verification pending

### Critical Implementation Gap
**The core feature is MISSING**: `_parse_rlm_section()` does NOT actually parse nested tables like [rlm.budget], [rlm.llm.root], etc. It only handles flat fields + partial sandbox.

**Next**: Implement ACTUAL nested section parsing.
