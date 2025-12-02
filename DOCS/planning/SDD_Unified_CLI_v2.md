# SDD: Unified CLI Productization (v2 - Phased)

**Author:** Antigravity (Gemini 2.0 Flash Experimental)  
**Date:** 2025-12-02  
**Status:** Draft  
**Roadmap Item:** 2.1 Productization and packaging  
**Protocol:** Dave Protocol (Significant Change - Requires HLD/SDD Approval)

---

## 1. Executive Summary

LLMC currently provides multiple entry points (`llmc-rag`, `llmc-tui`, `scripts/*.sh`, etc.) making discovery difficult and creating `bash → python` overhead. This SDD proposes a **phased migration** to a unified `llmc` command that wraps existing functionality while maintaining backwards compatibility.

**Key Principle:** **Wrap, don't replace.** `tools/rag/cli.py` (1176 lines, 15+ commands) is the proven, working RAG CLI. The unified CLI will be a thin orchestration layer, not a rewrite.

---

## 2. Current State Analysis

### 2.1 Existing Entry Points

| Command | Type | Implementation | Lines | Status |
|:--------|:-----|:---------------|------:|:-------|
| `llmc-rag` | Script wrapper | `scripts/llmc-rag` → `tools.rag.service` | 20 | Active |
| `llmc-tui` | Script wrapper | `scripts/llmc-tui` → `llmc.tui.app` | 16 | Active |
| `llmc-rag-daemon` | Daemon wrapper | `scripts/llmc-rag-daemon` | 973 | Active |
| `tools.rag.cli` | Click CLI | `python -m tools.rag.cli` | 1176 | **Primary RAG interface** |
| `llmc/cli.py` | Rich dashboard | Typer-based monitor (not a full CLI) | 276 | Demo/Prototype |
| `llmc-yolo`, `llmc-doctor`, etc. | pyproject.toml scripts | `llmcwrapper.cli.*` | Varies | Active |

### 2.2 Key Findings

1. **`tools/rag/cli.py` is production-ready**: Implements `index`, `sync`, `stats`, `graph`, `enrich`, `embed`, `search`, `plan`, `doctor`, `export`, `inspect`, and `nav` subcommand group.
2. **`llmc/cli.py` is NOT a CLI**: It's a Rich Live dashboard with 2 commands (`search` stub, `monitor` dashboard).
3. **TUI exists separately**: `llmc/tui/app.py` is the real TUI with screens for monitor, search, inspector, etc.
4. **Namespace split**: Core package is `llmcwrapper`, but scripts use `llmc-*` hyphenated names.

### 2.3 Dependencies

- **MCP Integration**: Active work on `llmc_mcp/server.py` per roadmap 1.7-1.8
- **Enrichment Pipeline**: Ongoing alignment work per roadmap 1.2
- **Config Centralization**: `llmc.toml` is the "single source of truth" (completed work from Nov 2025)

---

## 3. Goals & Non-Goals

### 3.1 Goals

1. **Single Entry Point**: `llmc` command as the "front door" for all operations
2. **Zero Regression**: All existing `llmc-*` commands continue to work
3. **Reduce Overhead**: Eliminate `bash → python` chains where practical
4. **Discoverability**: `llmc --help` shows all capabilities at a glance
5. **Installability**: `pip install -e . && llmc --version` works out of the box

### 3.2 Non-Goals

- **Rewriting `tools/rag/cli.py`**: It works. We wrap it, not replace it.
- **Breaking existing scripts**: Backwards compatibility is mandatory through at least 2 deprecation cycles.
- **Grand unification of `llmcwrapper` namespace**: That's a separate packaging refactor.
- **Replacing systemd or tmux workflows**: Service management wraps existing tools.

---

## 4. Design

### 4.1 Architecture

```
llmc                          # NEW: Unified CLI entry point
├── core.py                   # NEW: Shared utilities (config finder, version)
├── commands/                 # NEW: Command modules
│   ├── __init__.py
│   ├── init.py              # Bootstrap .llmc/ workspace
│   ├── rag.py               # Delegate to tools.rag.cli
│   ├── service.py           # Daemon management (wrap tools.rag.service)
│   ├── tui.py               # Launch llmc.tui.app
│   ├── mcp.py               # MCP server management (future)
│   └── doctor.py            # System health checks (aggregate)
└── main.py                   # NEW: Main entry point (Typer app)

# Existing (preserved, wrapped)
tools/rag/cli.py              # UNCHANGED: Primary RAG CLI
llmc/tui/app.py               # UNCHANGED: TUI application
scripts/llmc-rag              # DEPRECATED: Print warning, call `llmc rag`
scripts/llmc-tui              # DEPRECATED: Print warning, call `llmc tui`
```

### 4.2 Command Structure

```bash
llmc [GLOBAL_FLAGS] COMMAND [ARGS]
```

#### Core Commands (Phase 1)

| Command | Description | Implementation Strategy |
|:--------|:------------|:------------------------|
| `version` | Show version and paths | New (simple) |
| `help` | Show help | Built-in Typer |
| `init` | Bootstrap `.llmc/` workspace | New (uses `tools.rag.config`) |

#### RAG Commands (Phase 2)

| Command | Description | Delegation Target |
|:--------|:------------|:------------------|
| `index` | Index repository | `tools.rag.cli:index()` |
| `search` | Semantic search | `tools.rag.cli:search()` |
| `inspect` | Deep dive into symbol/file | `tools.rag.cli:inspect()` |
| `plan` | Generate retrieval plan | `tools.rag.cli:plan()` |
| `doctor` | RAG health check | `tools.rag.cli:doctor()` |
| `stats` | Index statistics | `tools.rag.cli:stats()` |

#### Service Commands (Phase 3)

| Command | Description | Implementation Strategy |
|:--------|:------------|:------------------------|
| `service start` | Start background daemon | Wrap `tools.rag.service` |
| `service stop` | Stop daemon | PID file management |
| `service status` | Check daemon status | PID + health check |
| `service logs` | Tail service logs | Read `.llmc/logs/service.log` |

#### UI Commands (Phase 2)

| Command | Description | Delegation Target |
|:--------|:------------|:------------------|
| `tui` | Launch interactive TUI | `llmc.tui.app:main()` |
| `monitor` | Alias for `tui` | Same as above |

### 4.3 Configuration Discovery

**Algorithm:**

1. Start at CWD
2. Walk up directory tree until:
   - `.llmc/` directory found → Use this as repo root
   - `.git/` directory found → Use this as repo root
   - Filesystem root reached → Error (not in a repo)
3. Load `llmc.toml` from repo root
4. If missing and command requires it, error with suggestion to run `llmc init`

**Implementation:** New module `llmc/core.py` with `find_repo_root()` and `load_config()`

### 4.4 Delegation Pattern

Commands delegate to existing implementations using **direct imports**, not subprocess calls:

```python
# llmc/commands/rag.py
from tools.rag.cli import cli as rag_cli
from click.testing import CliRunner

def search(query: str, limit: int = 10, json: bool = False):
    """Delegate to tools.rag.cli.search()"""
    runner = CliRunner()
    args = ["search", query, "--limit", str(limit)]
    if json:
        args.append("--json")
    result = runner.invoke(rag_cli, args)
    # Handle result.exit_code, result.output
```

**Alternative (cleaner):** Import the underlying functions directly:

```python
from tools.rag.search import search_spans
def search(query: str, limit: int = 10):
    results = search_spans(query, limit=limit, debug=False)
    # Format and display
```

**Decision:** Use **alternative approach** where possible to avoid Click-in-Typer nesting.

### 4.5 Backwards Compatibility

#### Deprecation Strategy

**Phase 1-2:** All existing commands work, print deprecation notice:
```
⚠️  llmc-rag is deprecated. Use 'llmc index' instead.
    This wrapper will be removed in LLMC v0.7.0 (est. Feb 2026).
```

**Phase 3:** Wrappers print louder warnings, add 1-second delay
**Phase 4:** Remove wrappers (2+ releases after unified CLI ships)

#### pyproject.toml Updates

```toml
[project.scripts]
# NEW unified entry point
llmc = "llmc.main:app"

# DEPRECATED (keep for backwards compat, will be removed in v0.7.0)
llmc-rag = "llmcwrapper.cli.llmc_rag:main"
llmc-tui = "llmcwrapper.cli.llmc_tui:main"
llmc-yolo = "llmcwrapper.cli.llmc_yolo:main"
llmc-doctor = "llmcwrapper.cli.llmc_doctor:main"
llmc-profile = "llmcwrapper.cli.llmc_profile:main"
```

---

## 5. Phased Implementation

### Phase 0: Foundation (Complexity: 2/10, Type: New Code)

**Goal:** Create minimal scaffolding with zero risk to existing functionality.

**Deliverables:**
- [ ] `llmc/core.py` - Config finder, version info
- [ ] `llmc/main.py` - Typer app with `--version` and `--help`
- [ ] `llmc/commands/__init__.py` - Empty package
- [ ] `pyproject.toml` update - Add `llmc = "llmc.main:app"`
- [ ] Install test - `pip install -e . && llmc --version`

**Tests:**
- `llmc --version` returns version string
- `llmc --help` shows usage
- `llmc nonexistent-command` shows helpful error

**Risk:** None (no existing code touched)  
**Effort:** 2 hours  
**Dependencies:** None

---

### Phase 1: Core Commands (Complexity: 4/10, Type: New Code)

**Goal:** Add basic, self-contained commands that don't depend on existing infrastructure.

**Deliverables:**
- [ ] `llmc/commands/init.py` - Bootstrap `.llmc/` workspace
  - Create `.llmc/` directory
  - Generate default `llmc.toml` (copy from template)
  - Initialize empty DB structure (`index_v2.db` schema)
  - Create log directory
- [ ] `llmc version` - Show version, paths, config status
  - Repo root
  - Config file location
  - Index status (exists? last updated?)
  - Python version, dependencies

**Tests:**
- `llmc init` in empty dir creates `.llmc/` and `llmc.toml`
- `llmc init` in existing `.llmc/` dir is idempotent
- `llmc version` shows accurate paths
- `llmc version --json` returns valid JSON

**Risk:** Low (new functionality only)  
**Effort:** 4 hours  
**Dependencies:** Phase 0

---

### Phase 2: RAG Command Delegation (Complexity: 6/10, Type: Integration)

**Goal:** Expose core RAG commands through unified CLI by delegating to existing implementations.

**Deliverables:**
- [ ] `llmc/commands/rag.py` - RAG command module
  - `llmc index` → `tools.rag.cli.index()`
  - `llmc search` → `tools.rag.search.search_spans()`
  - `llmc inspect` → `tools.rag.inspector.inspect_entity()`
  - `llmc plan` → `tools.rag.planner.generate_plan()`
  - `llmc stats` → `tools.rag.cli.stats()`
  - `llmc doctor` → `tools.rag.doctor.run_rag_doctor()`
- [ ] Argument translation layer (Click flags → Typer options)
- [ ] Output formatting (preserve existing formats exactly)

**Tests:**
- `llmc index` produces same output as `python -m tools.rag.cli index`
- `llmc search "query" --json` returns valid JSON matching schema
- `llmc doctor` exit codes match `tools.rag.cli doctor`
- All `tools/rag/tests/` tests still pass

**Risk:** Medium (integration complexity, must match existing behavior)  
**Effort:** 8 hours  
**Dependencies:** Phase 1

---

### Phase 3: TUI Integration (Complexity: 3/10, Type: Integration)

**Goal:** Launch TUI from unified CLI.

**Deliverables:**
- [ ] `llmc/commands/tui.py` - TUI launcher
  - `llmc tui` → `llmc.tui.app.main()`
  - `llmc monitor` → Alias for `llmc tui`
  - Pass through any TUI-specific flags

**Tests:**
- `llmc tui` launches TUI application
- TUI receives correct repo root from config discovery
- Exit code propagates correctly

**Risk:** Low (simple delegation)  
**Effort:** 2 hours  
**Dependencies:** Phase 1

---

### Phase 4: Service Management (Complexity: 8/10, Type: Integration + New Code)

**Goal:** Unified daemon lifecycle management.

**Deliverables:**
- [ ] `llmc/commands/service.py` - Service manager
  - `llmc service start` - Start daemon
    - Check if already running (PID file)
    - Launch `tools.rag.service` in background
    - Write PID to `.llmc/service.pid`
    - Tail logs for 3 seconds to verify startup
  - `llmc service stop` - Stop daemon
    - Read PID file
    - Send SIGTERM, wait 5s
    - Send SIGKILL if still alive
    - Remove PID file
  - `llmc service status` - Health check
    - Check PID file exists and process is alive
    - Check last heartbeat timestamp
    - Show uptime, last activity
  - `llmc service logs` - Tail logs
    - Read `.llmc/logs/service.log`
    - Support `--follow` flag
    - Support `--lines N` (default 50)
  - `llmc service restart` - Convenience wrapper

**Tests:**
- Start/stop/status lifecycle works correctly
- Stale PID files handled gracefully
- Multiple `start` calls detect already-running daemon
- `status` with dead daemon reports correctly
- Log tailing works with and without `--follow`

**Risk:** High (process management, race conditions, PID file handling)  
**Effort:** 12 hours  
**Dependencies:** Phase 1

**Note:** This may conflict with existing systemd integration. If systemd is present, `llmc service` should delegate to `systemctl` commands instead.

---

### Phase 5: Advanced RAG Commands (Complexity: 5/10, Type: Integration)

**Goal:** Expose remaining RAG commands.

**Deliverables:**
- [ ] Add to `llmc/commands/rag.py`:
  - `llmc sync` → `tools.rag.cli.sync()`
  - `llmc enrich` → `tools.rag.cli.enrich()`
  - `llmc embed` → `tools.rag.cli.embed()`
  - `llmc graph` → `tools.rag.cli.graph()`
  - `llmc export` → `tools.rag.cli.export()`
  - `llmc benchmark` → `tools.rag.cli.benchmark()`
- [ ] `llmc nav` subcommand group:
  - `llmc nav search`
  - `llmc nav where-used`
  - `llmc nav lineage`

**Tests:**
- All commands produce identical output to `tools.rag.cli` equivalents
- Argument translation is correct
- Exit codes match

**Risk:** Low (well-trodden path after Phase 2)  
**Effort:** 6 hours  
**Dependencies:** Phase 2

---

### Phase 6: Deprecation Warnings (Complexity: 3/10, Type: Modification)

**Goal:** Add deprecation notices to existing wrappers.

**Deliverables:**
- [ ] Modify `scripts/llmc-rag` to print warning and call `llmc rag`
- [ ] Modify `scripts/llmc-tui` to print warning and call `llmc tui`
- [ ] Update `llmcwrapper/cli/*.py` to print warnings
- [ ] Add deprecation timeline to `CHANGELOG.md`
- [ ] Update `README.md` to recommend `llmc` over legacy commands

**Tests:**
- Legacy commands still work
- Warning messages are clear and actionable
- Exit codes match new commands

**Risk:** Low (additive only)  
**Effort:** 3 hours  
**Dependencies:** Phases 2-5

---

### Phase 7: Documentation & Polish (Complexity: 4/10, Type: Documentation)

**Goal:** Make the unified CLI discoverable and well-documented.

**Deliverables:**
- [ ] Update `README.md` - Quick start with `llmc` commands
- [ ] Update `AGENTS.md` - RAG tooling reference section (replace `python -m tools.rag.cli` with `llmc`)
- [ ] Create `DOCS/CLI_REFERENCE.md` - Comprehensive command reference
- [ ] Add `llmc --help` text improvements
- [ ] Create migration guide for existing users
- [ ] Add shell completions (bash, zsh, fish)

**Tests:**
- Documentation examples all work
- Help text is accurate
- Shell completions install and work

**Risk:** None  
**Effort:** 6 hours  
**Dependencies:** Phases 1-6

---

### Phase 8: MCP Integration (Complexity: 7/10, Type: New + Integration)

**Goal:** Add MCP server management to unified CLI (future work, roadmap 1.7).

**Deliverables:**
- [ ] `llmc/commands/mcp.py` - MCP server manager
  - `llmc mcp start` - Start MCP server
  - `llmc mcp stop` - Stop MCP server
  - `llmc mcp status` - Check MCP server status
  - `llmc mcp logs` - Tail MCP logs

**Note:** Deferred to separate SDD. Listed here for completeness.

**Risk:** Medium  
**Effort:** 10 hours  
**Dependencies:** Roadmap 1.7 completion, Phases 1 & 4

---

## 6. Implementation Summary

### 6.1 Complexity & Effort Matrix

| Phase | Complexity | Type | Effort | Risk | Dependencies |
|:------|:----------:|:-----|-------:|:----:|:-------------|
| 0 - Foundation | 2/10 | New | 2h | None | - |
| 1 - Core | 4/10 | New | 4h | Low | P0 |
| 2 - RAG Delegation | 6/10 | Integration | 8h | Medium | P1 |
| 3 - TUI | 3/10 | Integration | 2h | Low | P1 |
| 4 - Service | 8/10 | Integration+New | 12h | High | P1 |
| 5 - Advanced RAG | 5/10 | Integration | 6h | Low | P2 |
| 6 - Deprecation | 3/10 | Modification | 3h | Low | P2-P5 |
| 7 - Docs | 4/10 | Documentation | 6h | None | P1-P6 |
| 8 - MCP | 7/10 | New+Integration | 10h | Medium | Roadmap 1.7 |

**Total effort (Phases 0-7):** ~43 hours  
**Total effort (including MCP):** ~53 hours

### 6.2 Recommended Sequencing

**Sprint 1 (MVP):** P0 → P1 → P2 → P3 (18h)
- Deliverable: `llmc version`, `llmc init`, `llmc search`, `llmc index`, `llmc tui` work

**Sprint 2 (Service):** P4 (12h)
- Deliverable: `llmc service` commands work

**Sprint 3 (Complete):** P5 → P6 → P7 (15h)
- Deliverable: All RAG commands available, deprecation warnings in place, docs updated

**Sprint 4 (Future):** P8
- Deliverable: MCP integration

---

## 7. Testing Strategy

### 7.1 Unit Tests

- [ ] `llmc/core.py` - Config discovery, version formatting
- [ ] `llmc/commands/init.py` - Workspace bootstrapping
- [ ] `llmc/commands/service.py` - PID management, process lifecycle

**Location:** `llmc/tests/test_cli_*.py`

### 7.2 Integration Tests

- [ ] Install test: `pip install -e . && llmc --version`
- [ ] Command delegation: Each `llmc` command produces same output as delegated target
- [ ] Backwards compat: `llmc-rag index` and `llmc index` produce identical results
- [ ] Service lifecycle: Start → status → logs → stop → status (clean shutdown)

**Location:** `tests/test_cli_integration.py`

### 7.3 Regression Tests

- [ ] All existing `tools/rag/tests/` tests pass
- [ ] All existing `llmc/tests/` tests pass
- [ ] All existing wrapper scripts (`scripts/llmc-*`) still work

### 7.4 Acceptance Criteria

**Before Phase 0-7 can be marked "Done":**
- [ ] `pip install -e .` creates working `llmc` command
- [ ] `llmc --help` shows all implemented commands
- [ ] `llmc index` and `python -m tools.rag.cli index` produce identical output
- [ ] `llmc service start && llmc service status` reports "running"
- [ ] All existing tests pass
- [ ] Documentation updated with `llmc` examples
- [ ] Deprecation warnings display for legacy commands

---

## 8. Risks & Mitigations

### 8.1 Process Management (Phase 4)

**Risk:** PID files, zombie processes, race conditions

**Mitigation:**
- Use `python-daemon` library for proper daemonization
- Implement robust PID file locking
- Add timeout handling for stop operations
- Test heavily on Linux (target platform per user info)

### 8.2 Argument Translation (Phases 2, 5)

**Risk:** Click → Typer argument mapping errors, behavioral differences

**Mitigation:**
- Import underlying functions directly (avoid CLI-in-CLI nesting)
- Write comprehensive integration tests comparing outputs
- Use `typer.testing.CliRunner` to test CLI layer independently

### 8.3 Backwards Compatibility (Phase 6)

**Risk:** Breaking existing user scripts, automation, CI/CD

**Mitigation:**
- Keep legacy commands working for at least 2 releases (6+ months)
- Clear deprecation timeline in warnings and `CHANGELOG.md`
- Provide migration guide with examples

### 8.4 Config Discovery Edge Cases (Phase 1)

**Risk:** Ambiguity when multiple `.llmc/` dirs exist in parent paths

**Mitigation:**
- Use **first** `.llmc/` or `.git/` found (nearest ancestor)
- Add `--repo` flag to explicitly override
- Error loudly if detection fails (don't guess)

---

## 9. Open Questions

1. **Systemd Integration:** If systemd service exists, should `llmc service` delegate to `systemctl` or manage processes directly?
   - **Recommendation:** Detect systemd unit, delegate if present, else use PID file approach

2. **`llmcwrapper` Namespace:** Should we eventually migrate to a pure `llmc` package namespace?
   - **Recommendation:** Defer to separate packaging refactor SDD (out of scope here)

3. **MCP Priority:** Is MCP integration (Phase 8) in scope for this SDD or a separate roadmap item?
   - **Recommendation:** List it here as Phase 8 but implement via separate SDD per roadmap 1.7

4. **Shell Completions:** Which shells should we support?
   - **Recommendation:** Start with bash/zsh (most common on Linux), add fish if requested

---

## 10. Success Metrics

**User Experience:**
- [ ] New user can run `llmc init && llmc index && llmc search "query"` without reading docs
- [ ] `llmc --help` is sufficient for discovery (no need to know about `python -m tools.rag.cli`)

**Performance:**
- [ ] `llmc` command startup < 100ms (current `bash → python` chains ~200-500ms)
- [ ] Zero overhead on delegated commands (within ±5% of direct calls)

**Quality:**
- [ ] Zero regressions (all existing tests pass)
- [ ] Test coverage > 80% for new code in `llmc/` module

**Adoption:**
- [ ] README uses `llmc` commands in all examples
- [ ] Deprecation warnings seen but don't block existing workflows
- [ ] Migration guide published and linked from `CHANGELOG.md`

---

## 11. Appendix: Example Usage

### Before (Current State)
```bash
# Fragmented, hard to discover
python -m tools.rag.cli index
python -m tools.rag.cli search "jwt verification"
scripts/llmc-tui
scripts/llmc-rag-daemon start
```

### After (Unified CLI)
```bash
# Clean, discoverable, installable
llmc init                     # Bootstrap workspace
llmc index                    # Index repo
llmc search "jwt verification"  # Semantic search
llmc tui                      # Launch TUI
llmc service start            # Start daemon
llmc service status           # Check health
```

### Backwards Compatibility (Phase 6)
```bash
$ llmc-rag index
⚠️  llmc-rag is deprecated. Use 'llmc index' instead.
    This wrapper will be removed in LLMC v0.7.0 (est. Feb 2026).

Indexed 42 files, 328 spans in 2.3s ...
```

---

## 12. Approval Checklist

Per **AGENTS.md** (Dave Protocol), this SDD requires approval before implementation:

- [ ] **Overview Confirmed:** Dave acknowledges goal and phasing strategy
- [ ] **HLD Approved:** Architecture (section 4) makes sense
- [ ] **SDD Approved:** Function signatures, delegation pattern, phases accepted
- [ ] **Test Strategy Approved:** Section 7 adequately covers risk
- [ ] **Migration Strategy Approved:** Backwards compat plan (section 4.5, phase 6) acceptable

**Next Steps After Approval:**
1. Create feature branch `feature/unified-cli`
2. Implement Phase 0 (Foundation)
3. Run install test
4. Proceed to Phase 1 with explicit approval per phase (or batch approval for P0-P3)

---

**Document Status:** Ready for Review  
**Estimated Review Time:** 20-30 minutes (comprehensive read)  
**Blocking Issues:** None (informational gaps resolved via codebase audit)
