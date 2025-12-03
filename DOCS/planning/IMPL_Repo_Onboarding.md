# Implementation Plan: Automated Repository Onboarding

**Feature:** P0 Automated Repository Onboarding  
**Branch:** `feature/repo-onboarding-automation`  
**SDD:** [SDD_Repo_Onboarding_v2_Hardened.md](SDD_Repo_Onboarding_v2_Hardened.md)  
**Start Date:** 2025-12-03  
**Target Completion:** TBD

---

## Implementation Status

### Phase 0: Pre-Flight & Rollback Foundation (4-5h)
**Status:** ⏸️ Not Started

**Tasks:**
- [ ] Create `OnboardingTransaction` class in `tools/rag/onboarding.py`
- [ ] Implement `_preflight_check()` with all validations
- [ ] Add FileLock integration for daemon coordination
- [ ] Implement rollback handler with reverse-order cleanup
- [ ] Add --dry-run mode
- [ ] Unit tests for rollback scenarios

**Files to Create:**
- `tools/rag/onboarding.py` (new module for onboarding logic)
- `tools/rag/models.py` (extend with onboarding types)
- `tests/test_onboarding_preflight.py`
- `tests/test_onboarding_rollback.py`

**Dependencies:**
- `filelock` library (check if in requirements.txt)

---

### Phase 1: Core Onboarding Method (3-4h)
**Status:** ⏸️ Not Started

**Tasks:**
- [ ] Create `RAGService.onboard_repo()` method skeleton
- [ ] Wire Phase 1 (inspection) using existing `inspect_repo()`
- [ ] Wire Phase 2 (workspace) using existing `plan_workspace()` / `init_workspace()`
- [ ] Wire Phase 4 (registry) using existing `RegistryAdapter`
- [ ] Add basic success/error handling
- [ ] Unit tests for happy path

**Files to Modify:**
- `tools/rag/service.py` (add `onboard_repo()` method)

**Files to Create:**
- `tests/test_onboarding_core.py`

---

### Phase 2: Config with Multi-Repo Strategy (4-5h)
**Status:** ⏸️ Not Started

**Tasks:**
- [ ] Implement template discovery via `importlib.resources`
- [ ] Create embedded minimal config fallback
- [ ] Implement `_update_allowed_roots()` with merge logic
- [ ] Add existing config detection + merge/replace prompt
- [ ] Ship `llmc/templates/llmc.minimal.toml` as package data
- [ ] Unit tests for all merge scenarios

**Files to Create:**
- `llmc/templates/llmc.minimal.toml` (package data)
- `llmc/templates/__init__.py`
- `tools/rag/config_template.py` (template management)
- `tests/test_config_template.py`
- `tests/test_multi_repo_merge.py`

**Files to Modify:**
- `setup.py` or `pyproject.toml` (add package_data for templates)

---

### Phase 3: Indexing & Enrichment (3-4h)
**Status:** ⏸️ Not Started

**Tasks:**
- [ ] Implement `_run_initial_indexing()` using existing `process_repo()` logic
- [ ] Implement `_run_initial_enrichment()` with EnrichmentPipeline
- [ ] Add progress feedback and stats collection
- [ ] Add interactive prompt for enrichment
- [ ] Test with various repo sizes

**Files to Modify:**
- `tools/rag/service.py` (add indexing/enrichment methods)

**Files to Create:**
- `tests/test_onboarding_indexing.py`

---

### Phase 4: Health Check (2-3h)
**Status:** ⏸️ Not Started

**Tasks:**
- [ ] Implement `_run_health_check()` with 3 smoke tests:
  - MCP connectivity test
  - RAG query test (sample query returns results)
  - Enrichment chain reachability test
- [ ] Add `HealthCheckResult` dataclass
- [ ] Implement status reporting (healthy | degraded | failed)
- [ ] Unit tests for each check

**Files to Create:**
- `tools/rag/health.py` (health check logic)
- `tests/test_onboarding_health.py`

**Files to Modify:**
- `tools/rag/models.py` (add `HealthCheckResult`)

---

### Phase 5: Update Command (2-3h)
**Status:** ⏸️ Not Started

**Tasks:**
- [ ] Implement `llmc-rag-repo update` CLI command
- [ ] Add selective re-run logic (--reindex, --reenrich, --config-only)
- [ ] Wire to service layer methods
- [ ] Test idempotency with existing repos

**Files to Modify:**
- `tools/rag_repo/cli.py` (add `update` command)

**Files to Create:**
- `tests/test_update_command.py`

---

### Phase 6: CLI Integration (2h)
**Status:** ⏸️ Not Started

**Tasks:**
- [ ] Update `tools/rag_repo/cli.py::_cmd_add()` to delegate to service
- [ ] Add all CLI flags:
  - --yes (non-interactive)
  - --dry-run
  - --force (re-run)
  - --no-index, --no-enrich, --no-health
  - --template
  - --merge-roots
  - --json
- [ ] Update help text with examples
- [ ] Wire to `RAGService.onboard_repo()`

**Files to Modify:**
- `tools/rag_repo/cli.py`

---

### Phase 7: Testing (4-5h)
**Status:** ⏸️ Not Started

**Tasks:**
- [ ] Pre-flight edge case tests:
  - Non-existent repo
  - No write permission
  - Already onboarded (without --force)
  - Disk space low
  - Large repo warning
  - Symlink handling
- [ ] Rollback scenario tests:
  - Failure during workspace creation
  - Failure during indexing
  - Failure during enrichment
  - Daemon lock acquisition failure
- [ ] Multi-repo config tests:
  - First repo (no existing config)
  - Add second repo (merge)
  - Add third repo (replace with --merge-roots=false)
- [ ] Idempotency tests:
  - Re-run with --force
  - Update command on existing repo
- [ ] End-to-end integration tests:
  - Full onboarding flow
  - Health check success/failure
  - Dry-run mode

**Files to Create:**
- `tests/test_onboarding_edge_cases.py`
- `tests/integration/test_onboarding_e2e.py`

---

### Phase 8: Documentation (3h)
**Status:** ⏸️ Not Started

**Tasks:**
- [ ] Create user guide: `DOCS/GUIDES/Onboarding_New_Repos.md`
  - Quick start
  - All flags explained
  - Multi-repo workflow
  - Troubleshooting common issues
- [ ] Create migration guide: `DOCS/GUIDES/Migrating_Existing_Repos.md`
  - For users with manually-onboarded repos
  - How to use `update` command
- [ ] Update `README.md`:
  - One-command onboarding in quick start
  - Link to onboarding guide
- [ ] Update `CHANGELOG.md`
- [ ] Add docstrings to all public APIs

**Files to Create:**
- `DOCS/GUIDES/Onboarding_New_Repos.md`
- `DOCS/GUIDES/Migrating_Existing_Repos.md`

**Files to Modify:**
- `README.md`
- `CHANGELOG.md` (already updated)

---

## Timeline

**Total Estimated Effort:** 27-35 hours

**Recommended Sprint (5 days):**
- **Day 1 (6-7h):** Phases 0-1 (Pre-flight, rollback, core method)
- **Day 2 (7-8h):** Phase 2 (Config with multi-repo)
- **Day 3 (5-6h):** Phases 3-4 (Indexing, enrichment, health check)
- **Day 4 (4-5h):** Phases 5-6 (Update command, CLI integration)
- **Day 5 (7-8h):** Phases 7-8 (Testing, documentation)

**Buffer:** 2-3 hours for unexpected issues

---

## Dependencies

### External Libraries
- [ ] Verify `filelock` is in requirements.txt (for daemon coordination)
- [ ] Verify `importlib.resources` available (Python 3.7+, should be fine)

### Internal APIs to Verify
- [ ] `tools.rag.runner.run_sync` exists and has expected signature
- [ ] `tools.rag.runner.detect_changes` exists
- [ ] `tools.rag.config.index_path_for_write` exists
- [ ] `tools.rag.database.Database` has expected methods:
  - `get_file_count()`
  - `get_file_count_by_type()`
  - `get_pending_span_count()`
  - `get_enriched_span_count()`

---

## Risk Mitigation

### Technical Risks
1. **filelock not in deps**
   - **Likelihood:** Low
   - **Impact:** Medium
   - **Mitigation:** Check requirements.txt, add if missing
   
2. **Database API changes**
   - **Likelihood:** Low  
   - **Impact:** High
   - **Mitigation:** Verify APIs exist in Phase 1

3. **Template packaging issues**
   - **Likelihood:** Medium
   - **Impact:** Medium
   - **Mitigation:** Test with editable install, have embedded fallback

### Schedule Risks
1. **Estimate too optimistic**
   - **Likelihood:** Medium
   - **Impact:** Medium
   - **Mitigation:** 2-3h buffer, can reduce scope if needed

2. **Concurrent work on service.py**
   - **Likelihood:** Low
   - **Impact:** High
   - **Mitigation:** Feature branch, merge frequently

---

## Success Criteria

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

### Performance
- [ ] Pre-flight checks complete in <1s
- [ ] Dry-run completes in <2s
- [ ] Indexing time matches existing `process_repo()`

---

## Definition of Done

A feature is **DONE** when:
1. ✅ All tasks completed
2. ✅ All tests passing (unit + integration)
3. ✅ Documentation written
4. ✅ Code reviewed
5. ✅ Linting clean
6. ✅ Manual testing on 3+ repos:
   - Small repo (~100 files)
   - Medium repo (~1000 files)
   - Large repo (~10k files)
7. ✅ Merged to `main`

---

## Notes

### Design Decisions
- **Why filelock?** Need portable locking across *nix/Windows
- **Why importlib.resources?** Robust, works with wheels, no path assumptions
- **Why OnboardingTransaction?** Clean rollback abstraction, testable
- **Why health check as v1?** Critical for validating success, not "future"

### Future Enhancements (Post-v1)
- Template library with multiple profiles
- Onboarding profiles (--profile python-ml, --profile webapp)
- Background mode (--background starts daemon job)
- Status command (llmc-rag-repo status /path/to/repo)
- Resume support for interrupted onboardings

---

## Questions / Blockers

**None currently.** Ready to start implementation.

---

## Changelog

- **2025-12-03:** Created implementation plan from v2 hardened SDD
