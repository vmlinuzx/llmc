# Thunderdome Roadmap

## Phase 1: Core Infrastructure ✅ DONE
- [x] Create `thunderdome/` directory structure
- [x] Implement `lib/common.sh` shared helpers
- [x] Create new Emilia orchestrator with `--repo` support
- [x] Implement report rotation (current/previous/archive)
- [x] Migrate 107 stale reports to archive
- [x] Create demon template (`_template.sh`)

## Phase 2: Demon Migration ✅ DONE
- [x] `rem_testing.sh` - General ruthless testing (Gemini)
- [x] `rem_security.sh` - Security audits
- [x] `rem_gap.sh` - Test gap analysis
- [x] `rem_mcp.sh` - MCP tool testing
- [x] `rem_chaos.sh` - Chaos/fuzzing tests (stub)
- [x] `rem_concurrency.sh` - Race condition detection (stub)
- [x] `rem_config.sh` - Config validation (stub)
- [x] `rem_dependency.sh` - Dependency audits (stub)
- [x] `rem_documentation.sh` - Docs accuracy (stub)
- [x] `rem_performance.sh` - Performance tests (stub)
- [x] `rem_upgrade.sh` - Upgrade compatibility (stub)

## Phase 3: Prompt Extraction 🔄 IN PROGRESS
- [x] `rem_testing.md` - Rem testing prompt
- [x] `rem_security.md` - Security audit prompt
- [x] `rem_gap.md` - Gap analysis prompt
- [ ] `rem_mcp.md` - MCP testing prompt
- [ ] `rem_chaos.md` - Chaos testing prompt
- [ ] `rem_performance.md` - Performance testing prompt
- [ ] `roswaal.md` - Roswaal testing prompt

## Phase 4: Cleanup
- [ ] Remove old scripts from `tools/` (after verification)
- [ ] Update any external references (docs, workflows)
- [ ] Add backward-compat symlinks if needed

## Phase 5: Enhancements
- [ ] JSON structured output from demons for better parsing
- [ ] Integration with CI/CD pipelines
- [ ] Web dashboard for test results
- [ ] Slack/Discord notifications for P0 issues
- [ ] Cross-repo aggregate reporting
- [ ] Roswaal migration (MiniMax/Claude-based testing)

## Design Decisions

### DD-TD-001: Reports Stay in Target Repo
Reports are written to `<target_repo>/tests/REPORTS/`, not in thunderdome.
This allows thunderdome to be used across multiple repos without mixing reports.

### DD-TD-002: Two-Generation Retention
Only `current/` and `previous/` are kept. Historical reports go to `archive/`.
This prevents unbounded growth while preserving one comparison point.

### DD-TD-003: Standardized Naming
All reports follow `{agent}_{scope}_{YYYY-MM-DD}.md` format.
This enables programmatic parsing and comparison.

### DD-TD-004: Stub Demons
Demons without full prompts use minimal inline prompts.
They're functional but should be enhanced with proper prompt files.

---

## Current Status

**Functional:**
- Emilia orchestrator (full/quick/tmux modes)
- Rem testing, security, gap (with full prompts)
- Rem mcp, chaos, concurrency, config, dependency, documentation, performance, upgrade (stubs)

**Pending:**
- Old `tools/` scripts - ready for removal after testing
- Roswaal (MiniMax/Claude) - not yet migrated
