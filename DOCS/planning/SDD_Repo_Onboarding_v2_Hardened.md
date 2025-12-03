# Software Design Document: Automated Repository Onboarding (v2 - Hardened)

**Status:** Active Development  
**Priority:** P0 (Productization Critical)  
**Created:** 2025-12-03  
**Revised:** 2025-12-03 (Hardening Review)  
**Owner:** Core Team

---

## 0. Revision History

### v2 Changes (2025-12-03)
**Hardening improvements based on architecture review:**

1. **Added Phase 0: Pre-Flight Checks** - Validate before making any changes
2. **Idempotency Strategy** - Handle re-runs gracefully with state detection
3. **Rollback Mechanism** - Clean up on failure with transaction-style operations
4. **Concurrency Coordination** - Lock acquisition and daemon synchronization
5. **Multi-Repo Config Strategy** - Merge vs replace `allowed_roots` logic
6. **Simplified OnboardingResult** - `phases_completed` list instead of redundant booleans
7. **Added --dry-run Mode** - Preview without side effects
8. **Health Check as Phase 8** - Moved from "future" to v1 (critical)
9. **Template Discovery Hardening** - Use `importlib.resources` for robustness
10. **Added Update Command Design** - Separate `update` from `add` for partial re-runs
11. **Missing Risks Addressed** - Symlinks, permissions, disk space, large repos, interrupts

---

## 1. Executive Summary

**Problem:** Current `llmc-rag-repo add` only creates workspace structure, leaving 6+ manual setup steps. Additionally, existing implementation lacks:
- Idempotency (crashes on re-run)
- Rollback on failure  
- Concurrency safety with daemon
- Multi-repo configuration strategy
- Dry-run capability
- Production-ready validation

**Solution:** Service-layer orchestration (`RAGService.onboard_repo()`) with **defensive design**:
- **Phase 0**: Pre-flight checks (validate before touching anything)
- **Transaction-style rollback** on failure
- **State detection** for idempotent re-runs  
- **Lock coordination** with daemon
- **--dry-run** mode for safe preview
- **Phase 8 Health Check** validates MCP readiness

**Impact:**
- **1 command** → fully configured repo (vs 6+ manual steps)
- **Production-ready** with rollback, concurrency safety, validation
- **Idempotent** - safe to re-run
- **Observable** - --dry-run shows what will happen

---

## 2. Architecture Overview

### 2.1 Complete Flow (8 Phases + Rollback)

```
llmc-rag-repo add /path/to/repo [flags]
  ↓
Phase 0: PRE-FLIGHT CHECK 🆕
  ├─ Validate repo exists and is writable
  ├─ Check if already onboarded → handle accordingly
  ├─ Detect existing config → merge strategy
  ├─ Estimate file count, time, disk space
  ├─ Acquire daemon lock (if daemon running) 🆕
  └─ DRY-RUN: Stop here, print plan, exit

Phase 1: Inspection
  └─ inspect_repo() → RepoInspection

Phase 2: Workspace Creation
  ├─ plan_workspace()
  └─ init_workspace()
  └─ ROLLBACK POINT: Mark workspace created

Phase 3: Configuration
  ├─ Resolve template (package data > arg > minimal) 🆕
  ├─ Merge allowed_roots (multi-repo strategy) 🆕
  ├─ Generate llmc.toml
  └─ ROLLBACK POINT: Mark config created

Phase 4: Registry
  ├─ register_in_registry()
  └─ add_to_daemon_state()
  └─ ROLLBACK POINT: Mark registered

Phase 5: Initial Indexing
  ├─ Check disk space available 🆕
  ├─ run_initial_indexing()
  └─ ROLLBACK POINT: Mark indexed

Phase 6: Optional Enrichment
  ├─ Interactive prompt (unless --yes)
  ├─ run_initial_enrichment()
  └─ ROLLBACK POINT: Mark enriched

Phase 7: MCP Instructions
  └─ print_mcp_instructions()

Phase 8: HEALTH CHECK 🆕 (was "future enhancement")
  ├─ Test MCP connectivity to repo
  ├─ Validate RAG query returns results
  ├─ Check enrichment chain reachable
  └─ ROLLBACK: If critical checks fail

ROLLBACK HANDLER: 🆕
  ├─ Delete .rag/ if workspace created
  ├─ Remove llmc.toml if config generated
  ├─ Unregister from registry/daemon if registered
  ├─ Release daemon lock
  └─ Print clear error + how to retry
```

---

## 3. Phase Designs (Detailed)

### Phase 0: Pre-Flight Checks (NEW)

**Purpose:** Validate assumptions before making ANY changes to filesystem or state.

```python
@dataclass
class PreflightResult:
    """Pre-flight validation result."""
    success: bool
    repo_exists: bool
    is_writable: bool
    is_git_repo: bool  # Warning if false, not error
    
    # Onboarding state detection
    already_onboarded: bool
    existing_config: bool | Path  # False or path to existing llmc.toml
    
    # Resource checks
    file_count: int
    estimated_index_time: str  # "~2 minutes"
    disk_space_available_mb: int
    disk_space_required_mb: int  # Estimate for .rag/
    
    # Daemon coordination
    daemon_running: bool
    daemon_processing_this_repo: bool
    lock_acquired: bool
    
    # Blockers (if any)
    blockers: list[str]  # ["Not writable", "Disk full"]
    warnings: list[str]  # ["Not a git repo", "Large repo >100k files"]

def _preflight_check(
    self, 
    repo_path: Path,
    force: bool = False,
) -> PreflightResult:
    """
    Validate before making changes. Acquires daemon lock if needed.
    
    Returns:
        PreflightResult with validation status
        
    Raises:
        OnboardingBlockedError: If force=False and blockers exist
    """
    blockers = []
    warnings = []
    
    # 1. Basic filesystem checks
    if not repo_path.exists():
        blockers.append(f"Repository not found: {repo_path}")
    
    if not os.access(repo_path, os.W_OK):
        blockers.append(f"No write permission: {repo_path}")
    
    # 2. Idempotency check
    already_onboarded = (repo_path / ".rag").exists()
    if already_onboarded and not force:
        blockers.append(
            "Already onboarded. Use --force to re-run or "
            "'llmc-rag-repo update' for partial updates."
        )
    
    # 3. Existing config detection
    existing_config = repo_path / "llmc.toml"
    if existing_config.exists() and not force:
        warnings.append(
            f"llmc.toml already exists. Will merge allowed_roots. "
            "Use --force to overwrite."
        )
    
    # 4. Resource estimation
    file_count = sum(1 for _ in repo_path.rglob("*") if _.is_file())
    if file_count > 100_000:
        warnings.append(
            f"Large repository ({file_count:,} files). "
            "Indexing may take >10 minutes."
        )
    
    # Estimate disk space (rough heuristic: 1KB per file for .rag/)
    disk_required_mb = max(file_count // 1000, 10)  # Min 10MB
    stat = os.statvfs(repo_path)
    disk_available_mb = (stat.f_bavail * stat.f_frsize) // (1024 * 1024)
    
    if disk_available_mb < disk_required_mb * 2:  # 2x safety margin
        blockers.append(
            f"Low disk space: {disk_available_mb}MB available, "
            f"{disk_required_mb}MB required"
        )
    
    # 5. Daemon coordination (acquire lock)
    daemon_running = self.state.is_running()
    lock_acquired = False
    
    if daemon_running:
        # Check if daemon is currently processing this repo
        # (prevents race where we modify state mid-processing)
        lock_path = repo_path / ".rag" / "onboarding.lock"
        try:
            # Try to acquire lock (timeout 5s)
            # If daemon has repo locked, this will fail
            self._onboarding_lock = FileLock(lock_path, timeout=5)
            self._onboarding_lock.acquire()
            lock_acquired = True
        except Timeout:
            blockers.append(
                "Daemon is currently processing this repo. "
                "Wait for cycle to complete or stop daemon."
            )
    
    # 6. Symlink handling
    if repo_path.is_symlink():
        resolved = repo_path.resolve()
        warnings.append(
            f"Path is symlink → {resolved}. "
            "Using resolved path for allowed_roots."
        )
        repo_path = resolved
    
    if blockers:
        raise OnboardingBlockedError(blockers, warnings)
    
    return PreflightResult(
        success=len(blockers) == 0,
        blockers=blockers,
        warnings=warnings,
        # ... fill in all fields
    )
```

**Dry-Run Integration:**
```python
if dry_run:
    preflight = _preflight_check(repo_path, force=False)
    _print_dry_run_plan(preflight, repo_path)
    return OnboardingResult(dry_run=True, ...)  # Exit early
```

---

### Phase 3 Revision: Configuration (Multi-Repo Strategy)

**Problem:** Current design replaces `allowed_roots` → breaks multi-repo setups.

**Solution:** Merge strategy with deduplication.

```python
def _update_allowed_roots(
    config_path: Path,
    new_repo: Path,
    strategy: str = "merge",  # "merge" | "replace" | "separate"
) -> None:
    """
    Update allowed_roots in llmc.toml with multi-repo awareness.
    
    Strategies:
        merge: Add new repo to existing list (default)
        replace: Replace entire list with [new_repo]
        separate: Create repo-specific config (advanced)
    
    Args:
        config_path: Path to llmc.toml
        new_repo: New repository to add
        strategy: How to handle existing roots
    """
    if not config_path.exists():
        # First repo - create new config
        roots = [str(new_repo.resolve())]
    else:
        # Load existing config
        with open(config_path, "rb") as f:
            config = tomllib.load(f)
        
        existing_roots = config.get("mcp", {}).get("tools", {}).get("allowed_roots", [])
        new_root = str(new_repo.resolve())
        
        if strategy == "merge":
            # Add if not present (deduplicate)
            roots = list(dict.fromkeys(existing_roots + [new_root]))
        elif strategy == "replace":
            roots = [new_root]
        else:  # "separate"
            # Don't modify global config - create repo-local config
            return
    
    # Update config
    # (TOML writing - preserve comments, use tomlkit or custom writer)
    ...
```

**Per-Repo Config Strategy (Advanced):**

For users who want **isolated** configs per repo:

```bash
# Option 1: Global config with multiple repos
$HOME/.config/llmc/llmc.toml:
allowed_roots = ["/repo1", "/repo2", "/repo3"]

# Option 2: Per-repo configs (set LLMC_CONFIG per session)
/repo1/llmc.toml:  allowed_roots = ["/repo1"]
/repo2/llmc.toml:  allowed_roots = ["/repo2"]

# Use with: export LLMC_CONFIG=/repo2/llmc.toml
```

**Recommendation:** Default to **merge** strategy, document **separate** for advanced users.

---

### Rollback Handler (NEW)

**Transaction-style cleanup on failure:**

```python
class OnboardingTransaction:
    """Track onboarding progress for rollback on failure."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self.phases_completed: list[str] = []
        self.created_workspace = False
        self.created_config = False
        self.registered = False
        self.lock: FileLock | None = None
    
    def mark_phase(self, phase: str):
        """Mark a phase as completed."""
        self.phases_completed.append(phase)
        if phase == "workspace":
            self.created_workspace = True
        elif phase == "config":
            self.created_config = True
        elif phase == "registry":
            self.registered = True
    
    def rollback(self):
        """Roll back completed phases in reverse order."""
        print("❌ Onboarding failed. Rolling back...")
        
        # Reverse order cleanup
        if self.registered:
            print("  🔄 Unregistering from registry")
            registry.unregister_by_path(self.repo_path)
            self.state.remove_repo(str(self.repo_path))
        
        if self.created_config:
            config_path = self.repo_path / "llmc.toml"
            if config_path.exists():
                 # Keep backup
                backup = config_path.with_suffix(".toml.bak")
                if not backup.exists():
                    print(f"  💾 Backup config to {backup}")
                    shutil.copy(config_path, backup)
                print(f"  🗑️  Removing {config_path}")
                config_path.unlink()
        
        if self.created_workspace:
            workspace = self.repo_path / ".rag"
            if workspace.exists():
                print(f"  🗑️  Removing workspace {workspace}")
                shutil.rmtree(workspace)
        
        if self.lock:
            print("  🔓 Releasing lock")
            self.lock.release()
        
        print("✅ Rollback complete. Fix errors and retry.")

def onboard_repo(self, repo_path: Path, ...) -> OnboardingResult:
    """Onboard with transaction-style rollback."""
    
    tx = OnboardingTransaction(repo_path)
    
    try:
        # Phase 0: Pre-flight
        preflight = self._preflight_check(repo_path, force=force)
        tx.lock = preflight.lock  # Store for rollback
        
        # Phase 1-7: Execute
        ...
        tx.mark_phase("workspace")
        ...
        tx.mark_phase("config")
        ...
        
        # Success!
        return OnboardingResult(success=True, ...)
        
    except Exception as e:
        # Rollback and re-raise
        tx.rollback()
        return OnboardingResult(
            success=False,
            error=str(e),
            phases_completed=tx.phases_completed,
        )
```

---

### Phase 8: Health Check (Moved from "Future")

**Critical for v1** - Validates onboarding actually worked:

```python
@dataclass
class HealthCheckResult:
    """Post-onboarding health validation."""
    overall_status: str  # "healthy" | "degraded" | "failed"
    
    mcp_connectable: bool
    mcp_error: str | None
    
    rag_queryable: bool
    rag_sample_results: int  # Number of results from test query
    rag_error: str | None
    
    enrichment_reachable: bool
    enrichment_error: str | None

def _run_health_check(self, repo_path: Path) -> HealthCheckResult:
    """
    Validate onboarding success with smoke tests.
    
    Tests:
        1. MCP: Can connect to repo via llmc.toml config?
        2. RAG: Does sample query return results?
        3. Enrichment: Is LLM chain reachable?
    
    Returns:
        HealthCheckResult with per-component status
    """
    print("🏥 Running health check...")
    
    # Test 1: MCP connectivity
    mcp_ok = False
    mcp_error = None
    try:
        from llmc_mcp.config import load_config
        config = load_config(repo_path / "llmc.toml")
        if str(repo_path.resolve()) in config.tools.allowed_roots:
            mcp_ok = True
        else:
            mcp_error = "Repo not in allowed_roots"
    except Exception as e:
        mcp_error = str(e)
    
    # Test 2: RAG query
    rag_ok = False
    rag_results = 0
    rag_error = None
    try:
        from tools.rag.search import search_spans
        results = search_spans(repo_path, "test", limit=5)
        rag_results = len(results)
        rag_ok = rag_results > 0
        if not rag_ok:
            rag_error = "No results from test query (index may be empty)"
    except Exception as e:
        rag_error = str(e)
    
    # Test 3: Enrichment chain
    enrich_ok = False
    enrich_error = None
    try:
        from tools.rag.enrichment_router import build_router_from_toml
        router = build_router_from_toml(repo_path)
        # Just building router tests config loading
        enrich_ok = len(router.chains) > 0
        if not enrich_ok:
            enrich_error = "No enrichment chains configured"
    except Exception as e:
        enrich_error = str(e)
    
    # Determine overall status
    if mcp_ok and rag_ok and enrich_ok:
        status = "healthy"
    elif mcp_ok and rag_ok:
        status = "degraded"  # Enrichment optional
    else:
        status = "failed"
    
    return HealthCheckResult(
        overall_status=status,
        mcp_connectable=mcp_ok,
        mcp_error=mcp_error,
        rag_queryable=rag_ok,
        rag_sample_results=rag_results,
        rag_error=rag_error,
        enrichment_reachable=enrich_ok,
        enrichment_error=enrich_error,
    )
```

**Health check output:**
```
🏥 Running health check...
  ✅ MCP: Connectable
  ✅ RAG: Queryable (5 test results)
  ⚠️  Enrichment: Chain unreachable (ollama not running)

Overall Status: DEGRADED
  → Repo is usable for search, but enrichment unavailable.
  → Fix: Start ollama or update llmc.toml enrichment config.
```

---

## 4. Template Discovery (Hardened)

**Problem:** Current design assumes LLMC repo layout exists.

**Solution:** Use `importlib.resources` for package data.

```python
# Ship template as package data
# llmc/templates/llmc.minimal.toml

from importlib import resources
import tomllib

def _load_template(template_arg: Path | None = None) -> dict:
    """
    Load config template with robust discovery.
    
    Priority:
        1. Explicit --template argument
        2. Package data (llmc/templates/llmc.minimal.toml)
        3. Embedded minimal config (fallback)
    
    Returns:
        Parsed TOML dict
    """
    if template_arg and template_arg.exists():
        # User-provided template
        with open(template_arg, "rb") as f:
            return tomllib.load(f)
    
    try:
        # Package data (shipped with llmc)
        template_bytes = resources.read_binary("llmc.templates", "llmc.minimal.toml")
        return tomllib.loads(template_bytes.decode())
    except (FileNotFoundError, ModuleNotFoundError):
        # Fallback: embedded minimal config
        return _generate_minimal_config()

def _generate_minimal_config() -> dict:
    """Embedded minimal config as fallback."""
    return {
        "mcp": {
            "tools": {
                "allowed_roots": [],  # Will be filled in
                "enable_run_cmd": True,
            },
            "rag": {
                "jit_context_enabled": True,
                "default_scope": "repo",
                "top_k": 3,
            },
        },
        "enrichment": {
            "enabled": True,
            "default_chain": "local",
            "batch_size": 50,
            "chain": [
                {
                    "name": "local",
                    "provider": "ollama",
                    "model": "qwen2.5:7b-instruct",
                    "url": "http://localhost:11434",
                }
            ],
        },
    }
```

---

## 5. Simplified OnboardingResult

**Problem:** Redundant fields (`indexed: bool` AND `index_stats: dict`).

**Solution:** Use `phases_completed` list.

```python
@dataclass
class OnboardingStats:
    """Statistics from onboarding phases."""
    files_indexed: int = 0
    spans_created: int = 0
    spans_enriched: int = 0
    time_elapsed_seconds: float = 0.0

@dataclass
class OnboardingResult:
    """Result of repository onboarding."""
    success: bool
    repo_path: Path
    workspace_path: Path | None = None
    config_path: Path | None = None
    
    # What phases completed successfully
    phases_completed: list[str] = field(default_factory=list)
    # ["preflight", "workspace", "config", "registry", "index", "enrich", "health"]
    
    # Aggregate stats
    stats: OnboardingStats | None = None
    
    # Feedback
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    
    # Special modes
    dry_run: bool = False
    
    @property
    def indexed(self) -> bool:
        """Convenience: was indexing completed?"""
        return "index" in self.phases_completed
    
    @property
    def enriched(self) -> bool:
        """Convenience: was enrichment completed?"""
        return "enrich" in self.phases_completed
```

---

## 6. Update Command (NEW)

**Separate from `add` for idempotency and clarity.**

```bash
# Add: Full onboarding (fails if already exists)
llmc-rag-repo add /path/to/repo

# Update: Partial re-run (for existing repos)
llmc-rag-repo update /path/to/repo [--reindex] [--reenrich] [--config-only]
```

```python
def update(
    path: str,
    reindex: bool = False,
    reenrich: bool = False,
    config_only: bool = False,
    force: bool = False,
):
    """
    Update an existing onboarded repository.
    
    Use when you need to:
    - Regenerate llmc.toml (--config-only)
    - Re-run indexing (--reindex)
    - Re-run enrichment (--reenrich)
    
    Examples:
        llmc-rag-repo update /path/to/repo --config-only
        llmc-rag-repo update /path/to/repo --reindex --reenrich
    """
    repo_path = Path(path)
    
    if not (repo_path / ".rag").exists():
        print(f"❌ Not onboarded: {repo_path}")
        print("   Use 'llmc-rag-repo add' instead.")
        return 1
    
    service = RAGService(...)
    
    # Selective re-run
    if config_only:
        service._regenerate_config(repo_path, force=force)
    
    if reindex:
        service._run_initial_indexing(repo_path)
    
    if reenrich:
        service._run_initial_enrichment(repo_path)
    
    # Always run health check
    health = service._run_health_check(repo_path)
    _print_health_status(health)
    
    return 0
```

---

## 7. CLI Enhancements

### Updated `add` Command

```python
@cli_app.command()
def add(
    path: str,
    # Modes
    yes: bool = typer.Option(False, "--yes", "-y",
        help="Non-interactive mode"),
    dry_run: bool = typer.Option(False, "--dry-run",
        help="Preview without making changes"),
    force: bool = typer.Option(False, "--force",
        help="Re-run even if already onboarded"),
    
    # Phase control
    no_index: bool = typer.Option(False, "--no-index"),
    no_enrich: bool = typer.Option(False, "--no-enrich"),
    no_health: bool = typer.Option(False, "--no-health",
        help="Skip health check"),
    
    # Config
    template: Optional[str] = typer.Option(None, "--template"),
    merge_roots: bool = typer.Option(True, "--merge-roots",
        help="Merge with existing allowed_roots (vs replace)"),
    
    # Output
    json_output: bool = typer.Option(False, "--json"),
):
    """
    Add a new repository with automated onboarding.
    
    Pre-flight validation ensures:
    - Repository exists and is writable
    - Disk space available
    - Not already onboarded (unless --force)
    
    Phases:
        0. Pre-flight checks
        1. Workspace creation (.rag/)
        2. Config generation (llmc.toml)
        3. Registry + daemon state
        4. Initial indexing
        5. Optional enrichment (interactive prompt)
        6. MCP instructions
        7. Health check
    
    Examples:
        # Preview what will happen
        llmc-rag-repo add /path/to/repo --dry-run
        
        # Full onboarding with defaults
        llmc-rag-repo add /path/to/repo
        
        # Non-interactive (CI mode)
        llmc-rag-repo add /path/to/repo --yes --no-enrich
        
        # Re-run with force
        llmc-rag-repo add /path/to/repo --force
    """
```

---

## 8. Risk Register (Updated)

| Risk | Severity | Missing From v1 | Mitigation (v2) |
|------|----------|-----------------|-----------------|
| **Idempotency** | High | ✅ | Phase 0 detects existing state, --force flag |
| **Rollback on failure** | High | ✅ | OnboardingTransaction with phase tracking |
| **Daemon concurrency** | High | ✅ | FileLock acquisition in Phase 0 |
| **Multi-repo config** | High | ✅ | Merge strategy with deduplication |
| **Symlink handling** | Medium | ✅ | Resolve in Phase 0, warn user |
| **Permission denied** | High | ✅ | Check os.access() in Phase 0 |
| **Disk full** | Medium | ✅ | statvfs() check in Phase 0 |
| **Large repos (>100K files)** | High | ✅ | File count estimate + warning in Phase 0 |
| **User Ctrl+C** | Medium | ✅ | Transaction rollback on exception |
| **Template missing** | Medium | ✅ | Package data + embedded fallback |
| **No dry-run** | Medium | ✅ | --dry-run flag |
| **No health check** | Medium | ✅ | Phase 8 (moved from future) |

---

## 9. Implementation Phases (Revised)

### Phase 0: Pre-Flight \u0026 Rollback Foundation (4-5h)
- `OnboardingTransaction` class
- `_preflight_check()` with all validations
- FileLock integration for daemon coordination
- Rollback handler
- --dry-run mode

### Phase 1: Core Onboarding (3-4h)
- `RAGService.onboard_repo()` skeleton
- Phases 1-2 (inspection, workspace)
- Phase 4 (registry)

### Phase 2: Config with Multi-Repo Strategy (4-5h)
- Template discovery (package data)
- `_update_allowed_roots()` with merge logic
- Existing config detection + merge
- Unit tests for merge scenarios

### Phase 3: Indexing \u0026 Enrichment (3-4h)
- `_run_initial_indexing()`
- `_run_initial_enrichment()`
- Progress feedback

### Phase 4: Health Check (2-3h)
- `_run_health_check()` 
- MCP/RAG/Enrichment smoke tests
- Status reporting

### Phase 5: Update Command (2-3h)
- `llmc-rag-repo update` CLI
- Selective re-run logic
- Update without full onboarding

### Phase 6: CLI Integration (2h)
- Wire `add` command with all flags
- Wire `update` command
- Help text

### Phase 7: Testing (4-5h)
- Pre-flight edge cases
- Rollback scenarios
- Multi-repo config merging
- Idempotency (re-run tests)
- End-to-end with real repos

### Phase 8: Documentation (3h)
- User guide with all flags
- Troubleshooting section
- Migration guide for existing repos
- Update README

**Total Effort:** 27-35 hours (was 18-24h)  
**Reason:** Added defensive features for production readiness

---

## 10. Success Criteria (Updated)

✅ **Defensive Design:**
- Pre-flight checks prevent invalid operations
- Rollback on failure leaves no partial state
- Idempotent - safe to re-run with --force
- Daemon coordination prevents race conditions

✅ **Multi-Repo Support:**
- Merge strategy for allowed_roots
- Works with 1 repo, 10 repos, or 100 repos
- Clear documentation of global vs per-repo configs

✅ **Observable:**
- --dry-run shows plan without changes
- Health check validates success
- Clear error messages with remediation hints

✅ **Production Ready:**
- All edge cases handled (symlinks, permissions, disk space)
- Large repo warnings
- Interrupt-safe with rollback

✅ **Well-Tested:**
- Unit tests for all components
- Integration tests for rollback scenarios
- End-to-end with multi-repo setups

---

## 11. Open Questions (Resolved)

1. ✅ **Idempotency strategy:** Phase 0 detection + --force flag
2. ✅ **Rollback design:** OnboardingTransaction with phase tracking
3. ✅ **Multi-repo config:** Merge strategy (default), document alternatives
4. ✅ **Dry-run:** --dry-run flag, exits after Phase 0
5. ✅ **Health check:** Phase 8 (v1, not future)
6. ✅ **Template discovery:** Package data + embedded fallback
7. ✅ **Update vs add:** Separate `update` command for clarity

---

## 12. Migration from v1 SDD

**Key architectural changes:**
1. Added Phase 0 (pre-flight) - **NEW**
2. Added Phase 8 (health check) - **PROMOTED**
3. Simplified `OnboardingResult` - **BREAKING CHANGE**
4. Multi-repo config strategy - **ENHANCEMENT**
5. Template discovery hardening - **BUGFIX**
6. Rollback mechanism - **NEW**
7. Update command - **NEW**

**Backward compatibility:**
- CLI flags remain compatible
- Service layer API is new (no existing callers)
- Database schema unchanged

---

## 13. References

- Current implementation: `tools/rag_repo/cli.py::_cmd_add()`
- Service layer: `tools/rag/service.py::RAGService.process_repo()`
- Config: `llmc.toml`
- MCP Config: `llmc_mcp/config.py`
- Lock manager: Consider using `filelock` library (already in deps?)
