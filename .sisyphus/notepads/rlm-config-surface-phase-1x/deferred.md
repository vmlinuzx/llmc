# Deferred Tasks

## Task 4: Nested Config Views
**Status**: DEFERRED to Phase 1.X.1
**Reason**: Would require creating new dataclasses (BudgetConfig, SandboxConfig, etc.) and updating all call sites. Current flat RLMConfig works and is backward compatible.

**What would be needed**:
- Create `BudgetConfig`, `SandboxConfig`, `LLMConfig` dataclasses
- Add them as nested fields in RLMConfig
- Update session.py, sandbox, budget modules to use nested objects
- Migration risk: breaks existing direct field access

**Decision**: Flat RLMConfig with nested TOML parsing is sufficient for Phase 1.X MVP.

## Task 5: Complete Wiring
**Status**: PARTIALLY DONE, rest deferred
**What's wired**: session.py, sandbox interfaces, budget.py, nav
**What's NOT wired**: prompts.py templates, additional nav defaults, trace formatting

**Decision**: Core subsystems (budget, sandbox, session) are wired. Remaining items are nice-to-have.
