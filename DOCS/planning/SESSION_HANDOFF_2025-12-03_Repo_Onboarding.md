# Session Handoff: Automated Repository Onboarding Feature

**Date:** 2025-12-03  
**Session Duration:** ~2 hours  
**Branch:** `feature/repo-onboarding-automation`  
**Status:** Planning Complete - Ready for Implementation

---

## 🎯 Executive Summary

**What We Built:**
Completed full planning and architecture for **P0 Automated Repository Onboarding** - a critical productization feature that eliminates the 6+ manual steps currently required to add a new repository to LLMC.

**Current State:**
- ✅ Planning complete (SDD v2 hardened)
- ✅ Implementation tracker created
- ✅ Roadmap updated (P0)
- ✅ Changelog updated
- ✅ Feature branch created
- ⏸️ Implementation not started yet

---

## 📋 What Was Accomplished

### 1. Identified The Problem (Conversation)
User asked: *"If I start antigravity in a new repo, will it just work?"*

**Answer:** No. Current issues:
- `llmc-rag-repo add` only creates workspace structure
- User must manually:
  1. Copy/generate `llmc.toml`
  2. Update `allowed_roots` for MCP
  3. Run initial indexing
  4. Run enrichment
  5. Update Claude Desktop config
  6. Restart MCP daemon

**Architecture problem:** Business logic in CLI instead of service layer.

### 2. Created Initial SDD (v1)
**File:** `DOCS/planning/SDD_Repo_Onboarding_Automation.md`

Designed service-layer orchestration with 7 phases.

### 3. Received Architectural Review
User provided **ruthless structural review** identifying 11 critical gaps:
1. Missing idempotency strategy
2. No rollback/cleanup on failure
3. Concurrency gap with daemon
4. `allowed_roots` accumulation problem (multi-repo)
5. Overly complex `OnboardingResult`
6. Missing --dry-run mode
7. Health check should be v1, not "future"
8. Tight coupling to LLMC repo layout
9. Interactive prompts block pipeline
10. Missing risk considerations
11. No update command for partial re-runs

### 4. Created Hardened v2 SDD
**File:** `DOCS/planning/SDD_Repo_Onboarding_v2_Hardened.md`

**Major additions:**
- **Phase 0: Pre-Flight Checks** - Validate before touching anything
  - Filesystem validation (exists, writable, disk space)
  - Idempotency detection (already onboarded?)
  - Daemon lock acquisition
  - Symlink resolution
  
- **Transaction-Style Rollback** - `OnboardingTransaction` class
  - Phase tracking
  - Reverse-order cleanup on failure
  - Lock release
  
- **Multi-Repo Config Strategy**
  - Merge vs replace `allowed_roots`
  - Deduplication
  - Per-repo config support
  
- **Phase 8: Health Check** (promoted from "future")
  - MCP connectivity test
  - RAG query validation
  - Enrichment chain reachability
  
- **--dry-run Mode** - Preview without side effects
- **Update Command Design** - Separate from `add` for partial re-runs
- **Template Discovery Hardening** - `importlib.resources` + embedded fallback

**Effort:** 27-35 hours (up from 18-24h, worth it for production quality)

### 5. Created Implementation Tracker
**File:** `DOCS/planning/IMPL_Repo_Onboarding.md`

8-phase breakdown with:
- Task checklists
- Time estimates per phase
- Files to create/modify
- Dependencies to verify
- Risk mitigation
- 5-day sprint schedule
- Success criteria

### 6. Updated Project Documentation
- **Roadmap:** Added as Section 1.1 (P0 priority)
- **Changelog:** Added to [Unreleased] section

### 7. Git State
```bash
Branch: feature/repo-onboarding-automation

Commits:
1. feat: Add P0 Automated Repository Onboarding to roadmap
2. docs: Add hardened v2 SDD for Automated Repository Onboarding  
3. docs: Add implementation tracker for Repo Onboarding
```

---

## 🗂️ Key Files Reference

### Planning Documents
| File | Purpose | Status |
|------|---------|--------|
| `DOCS/planning/SDD_Repo_Onboarding_v2_Hardened.md` | Architecture design (v2 hardened) | ✅ Complete |
| `DOCS/planning/IMPL_Repo_Onboarding.md` | Implementation tracker | ✅ Complete |
| `DOCS/ROADMAP.md` | Added Section 1.1 (P0) | ✅ Updated |
| `CHANGELOG.md` | Added [Unreleased] entry | ✅ Updated |

### Implementation Files (To Be Created)
| File | Purpose | Status |
|------|---------|--------|
| `tools/rag/onboarding.py` | Core onboarding logic | ⏸️ Not started |
| `tools/rag/health.py` | Health check implementation | ⏸️ Not started |
| `tools/rag/config_template.py` | Template management | ⏸️ Not started |
| `llmc/templates/llmc.minimal.toml` | Package data template | ⏸️ Not started |
| `tests/test_onboarding_*.py` | Unit tests | ⏸️ Not started |

### Files to Modify
| File | Changes Needed | Status |
|------|----------------|--------|
| `tools/rag/service.py` | Add `onboard_repo()` method | ⏸️ Not started |
| `tools/rag/models.py` | Add onboarding dataclasses | ⏸️ Not started |
| `tools/rag_repo/cli.py` | Wire `add` and `update` commands | ⏸️ Not started |
| `setup.py` or `pyproject.toml` | Add package_data for templates | ⏸️ Not started |

---

## 🚀 Next Steps (Priority Order)

### Immediate Next Session Should:

#### 1. **Verify Dependencies** (15 min)
```bash
cd /home/vmlinux/src/llmc
grep -r "filelock" requirements.txt pyproject.toml setup.py

# If not found, add:
pip install filelock
# Add to requirements.txt
```

#### 2. **Verify Existing APIs** (30 min)
Check that these exist with expected signatures:
```python
# In tools/rag/runner.py
from tools.rag.runner import run_sync, detect_changes

# In tools/rag/config.py
from tools.rag.config import index_path_for_write

# In tools/rag/database.py
from tools.rag.database import Database
# Check methods: get_file_count(), get_pending_span_count(), etc.
```

**Reference:** `DOCS/planning/IMPL_Repo_Onboarding.md` section "Dependencies → Internal APIs to Verify"

#### 3. **Start Phase 0 Implementation** (4-5 hours)
Create core infrastructure:

```bash
# Create new modules
touch tools/rag/onboarding.py
touch tools/rag/health.py
touch tests/test_onboarding_preflight.py
touch tests/test_onboarding_rollback.py

# Create template directory
mkdir -p llmc/templates
touch llmc/templates/__init__.py
```

**First code to write:**
1. `OnboardingTransaction` class in `tools/rag/onboarding.py`
2. `PreflightResult` dataclass in `tools/rag/models.py`
3. `_preflight_check()` method skeleton

**Reference:** `DOCS/planning/SDD_Repo_Onboarding_v2_Hardened.md` → "Phase 0: Pre-Flight Checks"

---

## 🔑 Key Architectural Decisions

### Decision 1: Service-Layer Orchestration
**Why:** Business logic belongs in service layer, not CLI  
**Impact:** `RAGService.onboard_repo()` is the one true path  
**Trade-off:** More upfront work, but cleaner architecture

### Decision 2: Transaction-Style Rollback
**Why:** Production systems need cleanup on failure  
**Impact:** No partial state left behind on error  
**Implementation:** `OnboardingTransaction` class tracks phases

### Decision 3: Multi-Repo Config Strategy (Merge)
**Why:** Users will have multiple repos  
**Impact:** `allowed_roots` merges instead of replaces  
**Alternative:** Per-repo configs for advanced users (documented)

### Decision 4: Health Check in v1
**Why:** Validating success is critical, not "nice to have"  
**Impact:** Phase 8 runs smoke tests (MCP, RAG, enrichment)  
**Trade-off:** +2-3 hours implementation time, worth it

### Decision 5: --dry-run Mode
**Why:** Users need to preview before committing  
**Impact:** Pre-flight runs, prints plan, exits  
**Implementation:** Simple flag, exits after Phase 0

---

## 🎯 Success Criteria (Copy from Tracker)

### Functional
- [ ] One command onboards a new repo completely
- [ ] --dry-run shows accurate preview
- [ ] Rollback works correctly on any failure
- [ ] Multi-repo config merging works
- [ ] Health check validates MCP readiness
- [ ] Update command allows selective re-runs

### Quality
- [ ] 100% test coverage on new code
- [ ] All edge cases tested
- [ ] No regressions in existing functionality
- [ ] Clean linting (ruff, mypy)

### Documentation
- [ ] User guide complete with examples
- [ ] Migration guide for existing users
- [ ] README updated
- [ ] All public APIs documented

---

## ⚠️ Known Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| `filelock` not in deps | Check/add in dependency verification step |
| Database API mismatch | Verify signatures before Phase 3 |
| Template packaging issues | Have embedded fallback config |
| Concurrent work on `service.py` | Feature branch isolation |

---

## 📚 Essential Context for Next Session

### What The Feature Does
Automates the entire repository onboarding process:
- **Before:** 6+ manual steps, error-prone, inconsistent
- **After:** `llmc-rag-repo add /path/to/repo` → fully ready for MCP

### Why It's P0
**Productization blocker.** This is the #1 UX friction point preventing:
- Smooth multi-repo workflows
- Adoption by other developers
- Professional "just works" experience

### Architecture Pattern
```
CLI (thin wrapper)
  ↓
Service Layer (business logic)
  ↓
Existing Components (workspace, registry, indexing)
```

### The 8 Phases
0. **Pre-flight** - Validate before touching anything
1. **Inspection** - Use existing `inspect_repo()`
2. **Workspace** - Create `.rag/` structure
3. **Config** - Generate `llmc.toml` with merged `allowed_roots`
4. **Registry** - Register with daemon
5. **Indexing** - Initial sync
6. **Enrichment** - Optional first batch
7. **Instructions** - Print MCP setup guide
8. **Health Check** - Validate it worked

### Transaction Safety
Every phase marks progress in `OnboardingTransaction`. On failure:
- Rollback in reverse order
- Clean up filesystem changes
- Release locks
- Print clear error with retry instructions

---

## 🔗 Quick Reference Links

### Must-Read Before Coding
1. **v2 SDD:** `DOCS/planning/SDD_Repo_Onboarding_v2_Hardened.md`
   - Read sections 3-7 (phases, rollback, health check)
   
2. **Implementation Tracker:** `DOCS/planning/IMPL_Repo_Onboarding.md`
   - Phase 0 task list
   - Dependencies section

### Existing Code to Study
1. `tools/rag_repo/cli.py::_cmd_add()` - Current (limited) implementation
2. `tools/rag/service.py::process_repo()` - Indexing/enrichment logic to reuse
3. `tools/rag_repo/workspace.py` - Workspace creation (reuse as-is)
4. `llmc.toml` - Template config structure

---

## 💬 Session Notes & Insights

### User's Key Insight
*"Is this a problem with the CLI, or is it a problem with the llmc-rag-service.py? This should happen outside of the CLI and just be exposed in the CLI right?"*

**Answer:** Exactly right. Service layer owns the logic, CLI is just a thin presentation wrapper.

### Most Important Review Feedback
*"Missing idempotency strategy... This WILL happen."*

User was absolutely correct - addressed with Phase 0 detection + --force flag + update command.

### Design Philosophy
Production-ready means:
- Idempotent (safe to re-run)
- Transactional (rollback on failure)
- Observable (--dry-run, health check)
- Defensive (pre-flight validation)

**Not just "works on my machine"** - works for anyone, anywhere, with clear error messages.

---

## 🎬 Suggested First Commands for Next Session

```bash
# 1. Check current state
git branch  # Should be on feature/repo-onboarding-automation
git status  # Should be clean

# 2. Verify dependencies
grep -r "filelock" requirements.txt pyproject.toml setup.py

# 3. Check existing APIs exist
cd /home/vmlinux/src/llmc
python3 -c "from tools.rag.runner import run_sync, detect_changes; print('✅ APIs exist')"

# 4. Create module structure
touch tools/rag/onboarding.py
touch tools/rag/health.py
mkdir -p llmc/templates
touch llmc/templates/__init__.py

# 5. Start coding!
# Open tools/rag/onboarding.py and begin with OnboardingTransaction class
```

---

## ✅ Definition of "Ready to Code"

Next session can start implementation immediately if:
- [x] Planning documents exist and are complete
- [x] Feature branch created
- [x] Architecture decisions documented
- [x] Success criteria defined
- [x] Risk mitigation planned
- [ ] Dependencies verified (do this first next session)
- [ ] Existing API signatures confirmed (do this first next session)

**Estimated time to start coding:** 45 minutes (dependency check + API verification)

---

## 🏁 Final Status

**Planning:** 100% Complete ✅  
**Implementation:** 0% Complete ⏸️  
**Estimated Total Effort:** 27-35 hours  
**Branch:** `feature/repo-onboarding-automation`  
**Priority:** P0 (Productization Critical)

**Next session should:** Verify dependencies → Verify APIs → Start Phase 0 implementation

---

**Good luck! The groundwork is solid. Time to build.** 🚀
