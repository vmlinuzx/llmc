# Software Design Document: Automated Repository Onboarding

**Status:** Active Development  
**Priority:** P0 (Productization Critical)  
**Created:** 2025-12-03  
**Owner:** Core Team

---

## 1. Executive Summary

**Problem:** When adding a new repository to LLMC, users must manually:
1. Create workspace structure
2. Copy/generate `llmc.toml` configuration
3. Update `allowed_roots` for MCP access
4. Run initial indexing
5. (Maybe) run enrichment
6. Configure daemon to watch the repo

This creates friction and reduces system usability. **The current CLI is a thin wrapper that only does workspace creation**, leaving critical setup steps manual.

**Solution:** Implement a **service-layer onboarding flow** that automates the entire repository setup process with interactive prompts for user decisions.

**Impact:**
- **Developer Experience:** One command to onboard a new repo (vs. 6+ manual steps)
- **MCP Readiness:** Repos are automatically configured for Antigravity/Claude Desktop
- **Consistency:** All repos use validated, working configurations
- **Discoverability:** Users learn the system through interactive prompts

---

## 2. Current Architecture (The Problem)

### 2.1 Current Flow

```
User runs: llmc-rag-repo add /path/to/new/repo
  ↓
tools/rag_repo/cli.py::_cmd_add()
  ├─ inspect_repo()           ✅ Works
  ├─ plan_workspace()         ✅ Works  
  ├─ init_workspace()         ✅ Works
  ├─ register_in_registry()   ✅ Works
  └─ notify_refresh()         ✅ Works
  
❌ STOPS HERE - User must manually:
  1. Copy llmc.toml to new repo
  2. Update allowed_roots = ["/path/to/new/repo"]
  3. Run: llmc-cli index
  4. Run: llmc-cli enrich (maybe?)
  5. Update Claude Desktop config
  6. Restart MCP daemon
```

### 2.2 Why This Is Wrong

**The CLI should be a thin wrapper.** All business logic belongs in the **service layer** (`tools/rag/service.py`), where:
- The RAG daemon already has `process_repo()` for indexing/enrichment
- State management exists (`ServiceState`)
- Configuration loading is centralized
- Error handling and logging are robust

**Current architecture violates separation of concerns:**
- CLI has business logic mixed with presentation
- Service layer is unaware of onboarding
- No single source of truth for "how to add a repo"

---

## 3. Proposed Architecture

### 3.1 New Flow

```
User runs: llmc-rag-repo add /path/to/new/repo [--auto]
  ↓
tools/rag_repo/cli.py::_cmd_add()
  ↓
  [THIN WRAPPER] Delegates to service:
  ↓
tools/rag/service.py::RAGService.onboard_repo()
  ├─ Phase 1: Inspection
  │   └─ inspect_repo() → RepoInspection
  ├─ Phase 2: Workspace Creation
  │   ├─ plan_workspace() → WorkspacePlan
  │   └─ init_workspace() ✅ Creates .rag/ structure
  ├─ Phase 3: Configuration
  │   ├─ copy_or_generate_llmc_toml() 🆕
  │   └─ update_allowed_roots() 🆕
  ├─ Phase 4: Registry
  │   ├─ register_in_registry() ✅ Existing
  │   └─ add_to_daemon_state() 🆕
  ├─ Phase 5: Initial Indexing
  │   ├─ run_initial_indexing() 🆕 (uses process_repo)
  │   └─ print_index_stats() 🆕
  ├─ Phase 6: Optional Enrichment
  │   ├─ [INTERACTIVE] Prompt: "Run enrichment? (Y/n)"
  │   └─ If yes: run_initial_enrichment() 🆕
  ├─ Phase 7: MCP Readiness
  │   └─ print_mcp_instructions() 🆕
  └─ Return: OnboardingResult
```

### 3.2 Key Components

#### 3.2.1 OnboardingResult (New Dataclass)

```python
@dataclass
class OnboardingResult:
    """Result of repository onboarding."""
    success: bool
    repo_path: Path
    workspace_path: Path
    config_path: Path | None
    
    # What was done
    workspace_created: bool
    config_generated: bool
    indexed: bool
    enriched: bool
    
    # Stats
    index_stats: dict[str, int] | None  # {files: N, code: N, docs: N}
    enrich_stats: dict[str, int] | None  # {spans: N, succeeded: N}
    
    # Errors/warnings
    warnings: list[str]
    error: str | None
```

#### 3.2.2 RAGService.onboard_repo() (New Method)

```python
class RAGService:
    def onboard_repo(
        self,
        repo_path: str | Path,
        *,
        interactive: bool = True,
        auto_index: bool = True,
        auto_enrich: bool | None = None,  # None = ask user
        template_toml: Path | None = None,
        skip_daemon: bool = False,
    ) -> OnboardingResult:
        """
        Complete repository onboarding with automated setup.
        
        This is the ONE TRUE ONBOARDING PATH. CLI tools delegate here.
        
        Args:
            repo_path: Path to repository to onboard
            interactive: If True, prompt user for decisions
            auto_index: If True, run initial indexing automatically
            auto_enrich: If None and interactive=True, ask user. 
                        Otherwise use boolean value.
            template_toml: Path to template llmc.toml 
                          (defaults to LLMC repo's toml)
            skip_daemon: If True, don't add to daemon state
            
        Returns:
            OnboardingResult with full status and stats
        """
```

---

## 4. Detailed Design

### 4.1 Phase 1: Inspection

**Existing functionality** (`tools/rag_repo/inspect_repo.py`):
```python
inspection = inspect_repo(repo_path, tool_config)
if not inspection.exists:
    return OnboardingResult(
        success=False,
        error=f"Repository not found: {repo_path}"
    )
```

### 4.2 Phase 2: Workspace Creation

**Existing functionality** (`tools/rag_repo/workspace.py`):
```python
plan = plan_workspace(repo_path, tool_config, inspection)
init_workspace(plan, inspection, tool_config, non_interactive=not interactive)
```

Creates:
```
/path/to/new/repo/.rag/
├── config/
│   ├── rag.yml
│   └── version.yml
├── index/
├── enrichments/
├── metadata/
├── logs/
└── tmp/
```

### 4.3 Phase 3: Configuration Setup (NEW)

#### 4.3.1 Copy or Generate llmc.toml

**New function:**
```python
def _copy_or_generate_llmc_toml(
    repo_path: Path,
    template_path: Path | None = None,
) -> Path:
    """
    Copy template llmc.toml to new repo with path updates.
    
    Logic:
    1. Use template_path if provided
    2. Otherwise use LLMC repo's llmc.toml as template
    3. Update all repo-specific paths:
       - [mcp.tools.allowed_roots]
       - [tool_envelope.workspace.root]
       - Any other absolute paths
    4. Write to repo_path/llmc.toml
    
    Returns:
        Path to generated llmc.toml
    """
```

**Template substitutions:**
```toml
# Template (LLMC repo)
[mcp.tools]
allowed_roots = ["/home/vmlinux/src/llmc"]

[tool_envelope.workspace]
root = "/home/vmlinux/src/llmc"

# Generated (new repo)
[mcp.tools]
allowed_roots = ["/path/to/new/repo"]

[tool_envelope.workspace]
root = "/path/to/new/repo"
```

**Edge cases:**
- If `llmc.toml` already exists → prompt to overwrite or merge
- If template is missing → generate minimal config with required fields only

#### 4.3.2 Minimal Config Template

If no template provided, generate minimal working config:

```toml
# Generated by llmc-rag-repo onboarding
# Edit as needed for your project

[mcp.tools]
allowed_roots = ["{REPO_PATH}"]
enable_run_cmd = true

[mcp.rag]
jit_context_enabled = true
default_scope = "repo"
top_k = 3

[enrichment]
enabled = true
default_chain = "local"
batch_size = 50

[[enrichment.chain]]
name = "local"
chain = "local"
provider = "ollama"
model = "qwen2.5:7b-instruct"
url = "http://localhost:11434"
```

### 4.4 Phase 4: Registry \u0026 State (HYBRID)

**Existing:** `RegistryAdapter.register(entry)`

**New:** Add to daemon state so it gets picked up on next cycle:
```python
def _add_to_daemon_state(self, repo_path: Path):
    """Add repo to daemon's watch list."""
    self.state.add_repo(str(repo_path))
    self.state.save()
    
    # Notify daemon to reload (if running)
    notify_refresh(
        RegistryEntry(repo_path=repo_path, ...),
        tool_config
    )
```

### 4.5 Phase 5: Initial Indexing (NEW)

**Leverage existing `process_repo()` logic:**

```python
def _run_initial_indexing(self, repo_path: Path) -> dict[str, int]:
    """
    Run initial sync and indexing for new repo.
    
    Uses existing process_repo() machinery but focused on indexing only.
    
    Returns:
        Stats: {files: N, code: N, docs: N, spans: N}
    """
    print(f"🔄 Running initial indexing for {repo_path.name}...")
    
    # Import from proper location
    from tools.rag.runner import run_sync, detect_changes
    from tools.rag.config import index_path_for_write
    from tools.rag.database import Database
    
    index_path = index_path_for_write(repo_path)
    
    # Detect all files (first run = everything is new)
    changes = detect_changes(repo_path, index_path=index_path)
    print(f"  📂 Found {len(changes)} files to index")
    
    # Sync to database
    run_sync(repo_path, changes)
    
    # Get stats
    db = Database(index_path)
    try:
        stats = {
            "files": db.get_file_count(),
            "code": db.get_file_count_by_type("code"),
            "docs": db.get_file_count_by_type("docs"),
            "spans": db.get_pending_span_count() + db.get_enriched_span_count(),
        }
    finally:
        db.close()
    
    print(f"  ✅ Indexed {stats['files']} files ({stats['code']} code, {stats['docs']} docs)")
    print(f"  📊 Created {stats['spans']} spans ready for enrichment")
    
    return stats
```

### 4.6 Phase 6: Optional Enrichment (NEW)

```python
def _run_initial_enrichment(
    self, 
    repo_path: Path,
    limit: int = 100,
) -> dict[str, int]:
    """
    Run initial enrichment batch for new repo.
    
    Args:
        repo_path: Repository path
        limit: Max spans to enrich in first batch
        
    Returns:
        Stats: {attempted: N, succeeded: N, failed: N}
    """
    print(f"🤖 Running initial enrichment (limit={limit})...")
    
    # Use EnrichmentPipeline exactly like process_repo() does
    from tools.rag.enrichment_pipeline import EnrichmentPipeline
    from tools.rag.enrichment_router import build_router_from_toml
    # ... (same setup as process_repo)
    
    result = pipeline.process_batch(
        limit=limit,
        stop_check=lambda: False,  # No interruption
    )
    
    print(f"  ✅ Enriched {result.succeeded}/{result.attempted} spans")
    if result.failed > 0:
        print(f"  ⚠️  {result.failed} failures (will retry later)")
    
    return {
        "attempted": result.attempted,
        "succeeded": result.succeeded,
        "failed": result.failed,
    }
```

**Interactive prompt:**
```python
if interactive and auto_enrich is None:
    response = input(
        "\n🤖 Run initial enrichment? "
        "This will use your configured LLM chain.\n"
        f"   First batch: {limit} spans\n"
        "   [Y/n]: "
    ).strip().lower()
    
    auto_enrich = response in ("", "y", "yes")
```

### 4.7 Phase 7: MCP Readiness Instructions (NEW)

```python
def _print_mcp_instructions(self, repo_path: Path, config_path: Path):
    """Print instructions for MCP/Antigravity integration."""
    print("\n" + "="*60)
    print("✅ Repository onboarded successfully!")
    print("="*60)
    print(f"\n📍 Repository: {repo_path}")
    print(f"📍 Config: {config_path}")
    print(f"📍 Workspace: {repo_path / '.rag'}")
    
    print("\n🚀 To use with Claude Desktop / Antigravity:")
    print("   1. Update your Claude Desktop config:")
    print(f'      "env": {{')
    print(f'        "LLMC_ROOT": "{repo_path}",')
    print(f'        "LLMC_CONFIG": "{config_path}"')
    print(f'      }}')
    print("\n   2. Restart Claude Desktop")
    print("   3. MCP queries will now use this repository's RAG graph")
    
    print("\n📚 Next steps:")
    print("   - Monitor enrichment: llmc service status")
    print("   - View stats: llmc-rag stats")
    print("   - Search: llmc-rag search 'your query'")
```

---

## 5. CLI Integration

### 5.1 Updated CLI Signature

```python
@cli_app.command()
def add(
    path: str,
    workspace: Optional[str] = None,
    yes: bool = typer.Option(False, "--yes", "-y", 
        help="Non-interactive mode (skip prompts)"),
    no_index: bool = typer.Option(False, "--no-index",
        help="Skip initial indexing"),
    no_enrich: bool = typer.Option(False, "--no-enrich",
        help="Skip initial enrichment"),
    template: Optional[str] = typer.Option(None, "--template",
        help="Path to template llmc.toml"),
    json_output: bool = typer.Option(False, "--json",
        help="Output JSON instead of human-readable"),
):
    """
    Add a new repository with automated onboarding.
    
    This will:
    - Create workspace structure (.rag/)
    - Generate llmc.toml configuration
    - Run initial indexing
    - (Optional) Run enrichment
    - Register with daemon
    
    Examples:
        llmc-rag-repo add /path/to/repo
        llmc-rag-repo add /path/to/repo --yes --no-enrich
        llmc-rag-repo add /path/to/repo --template custom.toml
    """
    tool_config = load_tool_config()
    
    # Create service instance
    state = ServiceState()
    tracker = FailureTracker()
    service = RAGService(state, tracker)
    
    # Delegate to service layer
    result = service.onboard_repo(
        repo_path=path,
        interactive=not yes,
        auto_index=not no_index,
        auto_enrich=None if not no_enrich else False,
        template_toml=Path(template) if template else None,
    )
    
    # Output
    if json_output:
        print(json.dumps(asdict(result), default=str))
    else:
        # Human-readable output handled by service
        pass
    
    return 0 if result.success else 1
```

---

## 6. Implementation Phases

### Phase 1: Core Onboarding Method (4-5 hours)
**Files:**
- `tools/rag/service.py`: Add `RAGService.onboard_repo()`
- `tools/rag/models.py`: Add `OnboardingResult` dataclass

**Tasks:**
1. Implement phases 1-2 (inspection, workspace) - largely wiring existing code
2. Implement phase 4 (registry) - use existing registry
3. Add basic success/error handling
4. Unit tests for happy path

### Phase 2: Configuration Generation (3-4 hours)
**Files:**
- `tools/rag/config_template.py` (new): Template management
- `tools/rag/service.py`: Add `_copy_or_generate_llmc_toml()`

**Tasks:**
1. Implement template loading and path substitution
2. Handle existing config (prompt to overwrite)
3. Generate minimal config fallback
4. Unit tests for all edge cases

### Phase 3: Initial Indexing (2-3 hours)
**Files:**
- `tools/rag/service.py`: Add `_run_initial_indexing()`

**Tasks:**
1. Wire existing `process_repo()` indexing logic
2. Add progress feedback
3. Collect and return stats
4. Test with various repo sizes

### Phase 4: Optional Enrichment (2-3 hours)
**Files:**
- `tools/rag/service.py`: Add `_run_initial_enrichment()`

**Tasks:**
1. Wire existing enrichment pipeline
2. Add interactive prompt
3. Implement batch limiting
4. Test with/without LLM availability

### Phase 5: MCP Instructions \u0026 Polish (2 hours)
**Files:**
- `tools/rag/service.py`: Add `_print_mcp_instructions()`

**Tasks:**
1. Format clear, actionable instructions
2. Add examples for common scenarios
3. Link to relevant docs

### Phase 6: CLI Integration (2 hours)
**Files:**
- `tools/rag_repo/cli.py`: Update `_cmd_add()` to delegate

**Tasks:**
1. Wire CLI args to service method
2. Add `--yes` for CI/automation
3. Add `--no-index`, `--no-enrich` flags
4. Update help text

### Phase 7: Testing \u0026 Documentation (3-4 hours)
**Files:**
- `tests/test_repo_onboarding.py` (new)
- `DOCS/GUIDES/Onboarding_New_Repos.md` (new)
- `README.md`: Update quick start

**Tasks:**
1. End-to-end test: onboard real repo
2. Test all flags and modes
3. Write user guide
4. Update README with one-command onboarding

---

## 7. Success Criteria

✅ **Automated Setup:**
- Single command onboards a new repo completely
- No manual file editing required

✅ **MCP Ready:**
- Generated `llmc.toml` has correct `allowed_roots`
- Instructions printed for Claude Desktop config
- Queries work immediately after onboarding

✅ **Interactive UX:**
- User prompted for enrichment decision
- Clear progress indicators
- Helpful error messages

✅ **Non-Interactive Mode:**
- `--yes` flag skips all prompts (CI-friendly)
- Sensible defaults for automation

✅ **Testing:**
- Unit tests for all phases
- End-to-end test with real repo
- Edge cases covered (existing config, missing template, etc.)

✅ **Documentation:**
- User guide with examples
- Updated README
- Inline help text

---

## 8. Future Enhancements

### 8.1 Template Library
- Ship multiple templates: `minimal.toml`, `full.toml`, `team.toml`
- `llmc-rag-repo templates list/show`

### 8.2 Onboarding Profiles
- Pre-configured profiles for common scenarios:
  - `--profile python-ml` (ML project with notebooks)
  - `--profile webapp` (frontend + backend)
  - `--profile monorepo` (complex structure)

### 8.3 Health Check
- Post-onboarding validation:
  - MCP connectivity test
  - Enrichment chain test
  - Sample query test

### 8.4 Migration Tool
- `llmc-rag-repo migrate <old-repo>` 
- Detect old manual setup
- Convert to new onboarding structure

---

## 9. Open Questions

1. **Template distribution:** Ship templates in repo or generate from code?
   - **Recommendation:** Ship `templates/llmc.minimal.toml` in repo
   
2. **Enrichment batch size:** What's a good default for first run?
   - **Recommendation:** 100 spans (fast feedback, not overwhelming)

3. **Daemon notification:** Should we auto-restart daemon if running?
   - **Recommendation:** Just notify, don't restart (safer)

4. **Config merge strategy:** How to handle existing `llmc.toml`?
   - **Recommendation:** Prompt with diff, offer backup

---

## 10. Risks \u0026 Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Template path substitution bugs | High | Extensive unit tests, validation |
| LLM not available during enrichment | Medium | Graceful failure, clear error message |
| Daemon state corruption | Medium | Atomic saves, validation on load |
| User interrupts during onboarding | Low | Idempotent operations, resume support |

---

## 11. Timeline

**Total Estimated Effort:** 18-24 hours

**Recommended Sprint:**
- Day 1 (4-5h): Phases 1-2 (core method, config generation)
- Day 2 (4-5h): Phases 3-4 (indexing, enrichment)
- Day 3 (3-4h): Phases 5-6 (MCP instructions, CLI)
- Day 4 (3-4h): Phase 7 (testing, docs)
- Day 5 (2-3h): Polish, edge cases, validation

**Deployment:**
- Merge to `main` after full test suite passes
- Update `CHANGELOG.md` with migration notes
- Announce in README with clear examples

---

## 12. References

- Current CLI: `tools/rag_repo/cli.py::_cmd_add()`
- Service layer: `tools/rag/service.py::RAGService.process_repo()`
- Registry: `tools/rag_repo/registry.py::RegistryAdapter`
- Workspace: `tools/rag_repo/workspace.py`
- Config: `llmc.toml`
