# Draft: RLM Configuration Surface Implementation

## Requirements (confirmed)
- **Hospital grade**: Must be production-ready, robust validation, fail-safe defaults
- Implement actual `load_rlm_config()` to parse `llmc.toml [rlm]` section
- Create nested config structures (BudgetConfig, SandboxConfig, LLMCallConfig, etc.)
- Thread config through all RLM components
- Add validation and schema with helpful error messages
- **92 hardcoded values** to extract (verified via code audit)

## User Decisions (2026-01-25)
| Decision | Choice | Rationale |
|----------|--------|-----------|
| Validation strictness | **Hybrid** | Hard fail on critical (budget, security). Warn-and-default on non-critical (timeouts, limits). |
| Environment overrides | **No, config file only** | Simpler to audit. All config in llmc.toml. |
| Security defaults | **Permissive** (CONFIGURABLE) | Default is permissive for local dev. Hospital deployments configure restrictive. Security policy is a config option, not hardcoded. |
| TDD | **Yes** | Hospital-grade quality requires comprehensive test coverage. |

## Metis Gap Analysis (incorporated)
| Gap | Resolution |
|-----|------------|
| Validation mismatch (current=ValueError, planned=warn-default) | Hybrid: critical params hard-fail, others warn-default |
| Security "permissive" vs hospital-grade | Make it configurable. Default=permissive, hospital sets restrictive in llmc.toml |
| TreeSitterNav breaking change | Only 2 callsites (session.py + tests). Make config optional. Safe. |
| Missing 50+ values from inventory | The explore agent found 92. Budget/sandbox/session/nav all covered. |

## Research Findings

### 1. Current load_rlm_config() (STUB)
**File**: `llmc/rlm/config.py:77-106`
- Already uses `llmc.core.load_config(find_repo_root())`
- Reads `[rlm]` section from llmc.toml
- Has `_parse_rlm_section()` that converts dict → RLMConfig dataclass
- **Missing**: Full parsing of nested sections, validation

### 2. Hardcoded Values Audit (92 total)
| Category | Count | Files |
|----------|-------|-------|
| Model names | 5 | config.py, budget.py |
| Budget/cost limits | 8 | config.py, budget.py |
| Timeout values | 5 | config.py, process_backend.py, interface.py |
| Context/size limits | 12 | config.py, session.py, treesitter_nav.py |
| LLM parameters | 5 | config.py |
| Security policies | 18 | config.py, process_backend.py |
| Magic numbers (truncation) | 24 | session.py, treesitter_nav.py |
| String literals | 15 | Various |

### 3. Existing LLMC Config Patterns
**Pattern used by agent/MCP/RLM**: Dataclass with field-by-field TOML parsing

```python
@dataclass
class SomeConfig:
    field: type = default  # Defaults hardcoded in dataclass

def load_some_config(path=None) -> SomeConfig:
    cfg = load_config(find_repo_root())  # Returns dict
    data = cfg.get("section", {})
    return _parse_section(data)  # Manual field extraction
```

**No Pydantic** - codebase uses stdlib dataclasses only.
**No env overrides** - consistent with user preference.

### 4. Component Threading Map
```
CLI (rlm.py)
  ↓
RLMConfig (load_rlm_config)
  ↓
RLMSession(config)
  ├─→ TokenBudget(BudgetConfig)  ← CONFIG THREADED ✅
  ├─→ create_sandbox(...)         ← CONFIG THREADED ✅
  └─→ TreeSitterNav(source)       ← NO CONFIG ❌
```

**TreeSitterNav needs config threading** - currently has 6+ hardcoded values.

## Scope Boundaries
- **INCLUDE**: All 92 hardcoded values moved to config
- **INCLUDE**: Warn-and-default validation
- **INCLUDE**: Full TOML schema documentation
- **INCLUDE**: Thread config to TreeSitterNav
- **EXCLUDE**: Environment variable overrides (user decision)
- **EXCLUDE**: Runtime hot-reload
- **EXCLUDE**: Config UI/TUI

## Technical Decisions
| Decision | Choice |
|----------|--------|
| Config structure | Dataclass hierarchy (matches existing pattern) |
| Validation | `.validate()` method on RLMConfig, logs warnings, uses defaults |
| Nested sections | `[rlm.budget]`, `[rlm.sandbox]`, `[rlm.llm]`, `[rlm.nav]` |
| Pricing table | `[rlm.pricing]` dict section (already partially exists) |
| Backward compat | Missing config = current defaults (no breaking changes) |

## Files to Modify
1. `llmc/rlm/config.py` - Main config, add nested dataclasses, validation
2. `llmc/rlm/nav/treesitter_nav.py` - Add config parameter to constructor
3. `llmc/rlm/session.py` - Thread config to TreeSitterNav
4. `llmc/rlm/governance/budget.py` - Remove duplicate defaults (use config)
5. `llmc/rlm/sandbox/process_backend.py` - Remove class-level defaults (use config)
6. `DOCS/reference/rlm-config.md` - New: Complete config reference
7. `docker/deploy/mcp/llmc.toml.example` - Add [rlm] section example
