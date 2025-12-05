# Implementation Plan: Deterministic Repo Docgen (v2)

**Status:** Planning  
**Priority:** P0 (Now)  
**SDD Reference:** [`SDD_Docgen_Enrichment_Module.md`](SDD_Docgen_Enrichment_Module.md)  
**Created:** 2025-12-03  

---

## Overview

Implement deterministic, RAG-aware documentation generation as a first-class enrichment stage. This will generate per-file documentation in `DOCS/REPODOCS/` with SHA256-based idempotence and graph context feeding.

**Key Goals:**
- ✅ Deterministic (same inputs → same outputs)
- ✅ Idempotent (skip unchanged files via SHA256 header)
- ✅ RAG-gated (only run when file is indexed and fresh)
- ✅ Graph-enriched (feed schema graph + enrichment context)
- ✅ Configurable backends (shell, LLM, HTTP, MCP)

---

## Phase Breakdown

### **Phase 1: Core Types & Config** 🟢 Easy
**Effort:** 2-3 hours  
**Files to create:**
- `llmc/docgen/__init__.py`
- `llmc/docgen/types.py`
- `llmc/docgen/config.py`

**Tasks:**
1. Define core types:
   ```python
   @dataclass
   class DocgenResult:
       status: str  # "noop" | "generated" | "skipped"
       sha256: str
       output_markdown: str | None
       reason: str | None = None
   
   class DocgenBackend(Protocol):
       def generate_for_file(...) -> DocgenResult: ...
   ```

2. Implement config loader:
   ```python
   def load_docgen_backend(
       repo_root: Path,
       toml_data: dict
   ) -> DocgenBackend | None:
       # Read [docs.docgen] section
       # Dispatch on backend type
       # Return appropriate backend instance
   ```

3. Add config schema to `llmc.toml`:
   ```toml
   [docs.docgen]
   enabled = false  # Start disabled
   backend = "shell"
   output_dir = "DOCS/REPODOCS"
   require_rag_fresh = true
   ```

**Tests:**
- Config parsing with valid/invalid backends
- Missing/disabled docgen section handling
- Backend factory dispatch

**Success Criteria:**
- ✅ Can load docgen config from `llmc.toml`
- ✅ Returns `None` when disabled
- ✅ Raises clear errors on invalid config

---

### **Phase 2: SHA Gating Logic** 🟢 Easy
**Effort:** 2 hours  
**Files to create:**
- `llmc/docgen/gating.py`

**Tasks:**
1. Implement SHA computation and comparison:
   ```python
   def compute_file_sha256(file_path: Path) -> str:
       # SHA256 hash of file contents
   
   def read_doc_sha256(doc_path: Path) -> str | None:
       # Read first line, extract SHA256: <hash>
       # Return None if missing or malformed
   
   def should_skip_sha_gate(
       source_path: Path,
       doc_path: Path
   ) -> tuple[bool, str]:
       # Returns (should_skip, reason)
       # True if doc exists and SHA matches
   ```

2. Implement doc path resolution:
   ```python
   def resolve_doc_path(
       repo_root: Path,
       relative_path: Path,
       output_dir: str = "DOCS/REPODOCS"
   ) -> Path:
       # repo_root / output_dir / relative_path.md
   ```

**Tests:**
- SHA computation matches expected values
- Doc SHA extraction from various formats
- Skip logic when SHA matches/differs/missing

**Success Criteria:**
- ✅ Can detect when doc is up-to-date via SHA
- ✅ Handles missing docs gracefully
- ✅ Handles malformed SHA headers

---

### **Phase 3: RAG Freshness Gating** 🟡 Medium
**Effort:** 3-4 hours  
**Files to modify:**
- `llmc/docgen/gating.py`

**Tasks:**
1. Implement RAG freshness check:
   ```python
   def check_rag_freshness(
       db: Database,
       relative_path: Path,
       file_sha256: str
   ) -> tuple[bool, str]:
       # Query RAG DB for file
       # Check if file_hash matches file_sha256
       # Returns (is_fresh, reason)
   ```

2. Query logic:
   - Check `files` table for matching path
   - Verify `file_hash == file_sha256`
   - Optionally check for spans/entities

3. Handle edge cases:
   - File not in RAG DB → `SKIP_NOT_INDEXED`
   - File hash mismatch → `SKIP_STALE_INDEX`
   - No spans for file → configurable (default: allow)

**Tests:**
- Fresh file (hash matches) → allowed
- Stale file (hash differs) → skipped
- Missing file → skipped
- Mock Database for testing

**Success Criteria:**
- ✅ Only allows docgen for RAG-indexed files
- ✅ Detects stale index state
- ✅ Clear skip reasons for debugging

---

### **Phase 4: Graph Context Builder** 🟡 Medium
**Effort:** 4-5 hours  
**Files to create:**
- `llmc/docgen/graph_context.py`

**Tasks:**
1. Implement graph context extraction:
   ```python
   def build_graph_context(
       repo_root: Path,
       relative_path: Path,
       db: Database
   ) -> str:
       # Load graph indices from .llmc/rag_graph.json
       # Find entities for this file
       # Find relations involving these entities
       # Fetch enrichment data if available
       # Format as deterministic text
   ```

2. Context format (deterministic):
   ```text
   === GRAPH_CONTEXT_BEGIN ===
   file: <relative_path>
   indexed_at: <iso_timestamp>
   entities:
     - id: <entity_id>
       kind: <kind>
       name: <symbol>
       span: <start>-<end>
       summary: <enrichment_summary>
   relations:
     - src: <entity_id>
       edge: CALLS
       dst: <entity_id>
   === GRAPH_CONTEXT_END ===
   ```

3. Integration with existing graph code:
   - Use `tools.rag.graph_index.load_indices()`
   - Use `tools.rag.graph_enrich.enrich_graph_entities()`
   - Deterministic ordering (sort by entity ID, then relation)

**Tests:**
- Graph context for file with entities
- Graph context for file without entities
- Deterministic output (same input → same output)
- Handle missing graph indices gracefully

**Success Criteria:**
- ✅ Builds deterministic graph context
- ✅ Includes entities and relations
- ✅ Includes enrichment summaries when available
- ✅ Handles missing graph data

---

### **Phase 5: Shell Backend** 🟢 Easy
**Effort:** 3 hours  
**Files to create:**
- `llmc/docgen/backends/__init__.py`
- `llmc/docgen/backends/shell.py`

**Tasks:**
1. Implement `ShellDocgenBackend`:
   ```python
   @dataclass
   class ShellDocgenBackend:
       script: Path
       args: list[str]
       timeout_seconds: int
       
       def generate_for_file(...) -> DocgenResult:
           # Build subprocess command
           # Pass data via stdin (JSON)
           # Capture stdout
           # Parse result (NO-OP or doc)
           # Validate SHA256 header
   ```

2. Input format (stdin JSON):
   ```json
   {
     "repo_root": "/path/to/repo",
     "relative_path": "tools/rag/database.py",
     "file_sha256": "abc123...",
     "source_contents": "...",
     "existing_doc_contents": "...",
     "graph_context": "=== GRAPH_CONTEXT_BEGIN ===\n..."
   }
   ```

3. Output parsing:
   - `NO-OP: SHA unchanged (abc123...)` → `status="noop"`
   - `SHA256: abc123...\n<markdown>` → `status="generated"`
   - Invalid output → error

4. Create example shell script:
   - `scripts/docgen_stub.sh` (for testing)
   - Echoes back a valid doc with SHA header

**Tests:**
- Shell backend with stub script
- NO-OP response handling
- Valid doc response handling
- Timeout handling
- Invalid output error handling

**Success Criteria:**
- ✅ Can invoke shell script with JSON input
- ✅ Parses NO-OP and generated responses
- ✅ Validates SHA256 header
- ✅ Handles timeouts and errors

---

### **Phase 6: Orchestrator** 🟡 Medium
**Effort:** 4-5 hours  
**Files to create:**
- `llmc/docgen/orchestrator.py`

**Tasks:**
1. Implement batch orchestrator:
   ```python
   class DocgenOrchestrator:
       def __init__(
           self,
           repo_root: Path,
           backend: DocgenBackend,
           db: Database,
           output_dir: str = "DOCS/REPODOCS"
       ): ...
       
       def process_file(
           self,
           relative_path: Path
       ) -> DocgenResult:
           # 1. Compute file SHA
           # 2. SHA gate check
           # 3. RAG freshness check
           # 4. Build graph context
           # 5. Invoke backend
           # 6. Write doc file (if generated)
           # 7. Return result
       
       def process_batch(
           self,
           file_paths: list[Path]
       ) -> dict[str, DocgenResult]:
           # Process files sequentially
           # Return results map
   ```

2. File writing logic:
   - Atomic write (tmp file + rename)
   - Create parent directories
   - Preserve existing docs on skip/noop

3. Logging and metrics:
   - Log each file: `GENERATED`, `NOOP`, `SKIPPED`
   - Track counts: total, generated, skipped, errors
   - Emit structured logs (JSON)

**Tests:**
- Process single file (all paths: noop, generated, skipped)
- Process batch of files
- Atomic file writing
- Directory creation
- Metrics tracking

**Success Criteria:**
- ✅ Processes files sequentially
- ✅ Applies both gates correctly
- ✅ Writes docs atomically
- ✅ Logs all outcomes clearly

---

### **Phase 7: CLI Integration** 🟢 Easy
**Effort:** 2-3 hours  
**Files to modify:**
- `llmc/commands/rag.py` (or new `llmc/commands/docs.py`)

**Tasks:**
1. Add CLI command:
   ```bash
   llmc debug autodoc generate [PATH]
   llmc debug autodoc generate --all
   llmc debug autodoc status
   ```

2. Implementation:
   ```python
   @app.command()
   def generate(
       path: str | None = None,
       all: bool = False,
       force: bool = False  # Ignore SHA gate
   ):
       # Load config
       # Create orchestrator
       # Discover files (single or all)
       # Process batch
       # Print summary
   ```

3. File discovery for `--all`:
   - Query RAG DB for all indexed files
   - Filter by extension (`.py`, `.ts`, `.js`, etc.)
   - Optionally filter by directory

4. Status command:
   ```bash
   llmc debug autodoc status
   # Shows:
   # - Total files in RAG
   # - Files with docs
   # - Files needing docs (stale SHA)
   # - Files skipped (not indexed)
   ```

**Tests:**
- CLI command parsing
- Single file generation
- Batch generation
- Status reporting

**Success Criteria:**
- ✅ Can generate docs via CLI
- ✅ Supports single file and batch modes
- ✅ Shows clear progress and summary

---

### **Phase 8: Concurrency Control** 🟡 Medium
**Effort:** 2-3 hours  
**Files to create:**
- `llmc/docgen/locks.py`

**Tasks:**
1. Implement per-repo lock:
   ```python
   class DocgenLock:
       def __init__(self, repo_root: Path):
           self.lock_file = repo_root / ".llmc" / "docgen.lock"
       
       def acquire(self, timeout: float = 0) -> bool:
           # Try to acquire file lock
           # Return False if already locked
       
       def release(self): ...
       
       def __enter__(self): ...
       def __exit__(self): ...
   ```

2. Integration with orchestrator:
   ```python
   def process_batch(self, file_paths):
       with DocgenLock(self.repo_root):
           # Process files
   ```

3. CLI behavior on lock conflict:
   - Default: fail fast with clear message
   - Optional: `--wait` flag to wait for lock

**Tests:**
- Lock acquisition and release
- Concurrent lock attempts (fail fast)
- Lock cleanup on error

**Success Criteria:**
- ✅ Only one docgen per repo at a time
- ✅ Clear error on lock conflict
- ✅ Lock released on error/completion

---

### **Phase 9: Daemon Integration** 🟡 Medium
**Effort:** 3-4 hours  
**Files to modify:**
- `tools/rag/service.py`

**Tasks:**
1. Add docgen stage to daemon loop:
   ```python
   def _daemon_loop(self):
       while not self._stop_event.is_set():
           # Existing: indexing, enrichment, embedding
           
           # New: docgen stage
           if self._should_run_docgen():
               self._run_docgen_batch()
   ```

2. Docgen scheduling logic:
   - Only run after enrichment is stable
   - Configurable interval (default: 1 hour)
   - Skip if lock is held

3. Batch size control:
   - Process N files per daemon tick (default: 10)
   - Avoid overwhelming LLM providers
   - Resume from last position

4. Configuration:
   ```toml
   [docs.docgen]
   enabled = true
   daemon_interval_seconds = 3600
   daemon_batch_size = 10
   ```

**Tests:**
- Daemon runs docgen stage
- Respects interval
- Respects batch size
- Skips when locked

**Success Criteria:**
- ✅ Daemon generates docs automatically
- ✅ Configurable interval and batch size
- ✅ Doesn't block other daemon work

---

### **Phase 10: Testing & Polish** 🟡 Medium
**Effort:** 4-5 hours  

**Tasks:**
1. Integration tests:
   - End-to-end: index → enrich → docgen
   - Verify doc files created correctly
   - Verify SHA headers match
   - Verify graph context included

2. Create example Gemini script:
   - `scripts/gemini_docgen.sh`
   - Calls Gemini API with fixed params
   - Returns formatted doc with SHA header
   - Include in repo as reference implementation

3. Documentation:
   - Update README with docgen section
   - Create `DOCS/Docgen_Usage.md` guide
   - Document backend configuration
   - Document graph context format

4. Error handling polish:
   - Clear error messages
   - Helpful suggestions (e.g., "Run `llmc index` first")
   - Graceful degradation

**Tests:**
- Full integration test suite
- Error message clarity
- Documentation accuracy

**Success Criteria:**
- ✅ All tests passing
- ✅ Clear documentation
- ✅ Example script works
- ✅ Helpful error messages

---

## Implementation Order

**Recommended sequence:**
1. Phase 1 (Types & Config) - Foundation
2. Phase 2 (SHA Gating) - Core logic
3. Phase 5 (Shell Backend) - Can test early
4. Phase 3 (RAG Gating) - Requires DB
5. Phase 4 (Graph Context) - Requires graph
6. Phase 6 (Orchestrator) - Ties it together
7. Phase 7 (CLI) - User-facing
8. Phase 8 (Locks) - Concurrency safety
9. Phase 9 (Daemon) - Automation
10. Phase 10 (Testing & Polish) - Ship it

**Parallel opportunities:**
- Phases 2 & 5 can be done in parallel
- Phases 3 & 4 can be done in parallel
- Phase 7 can start after Phase 6

---

## Estimated Total Effort

| Phase | Difficulty | Hours |
|-------|-----------|-------|
| 1. Types & Config | 🟢 Easy | 2-3 |
| 2. SHA Gating | 🟢 Easy | 2 |
| 3. RAG Gating | 🟡 Medium | 3-4 |
| 4. Graph Context | 🟡 Medium | 4-5 |
| 5. Shell Backend | 🟢 Easy | 3 |
| 6. Orchestrator | 🟡 Medium | 4-5 |
| 7. CLI Integration | 🟢 Easy | 2-3 |
| 8. Concurrency | 🟡 Medium | 2-3 |
| 9. Daemon Integration | 🟡 Medium | 3-4 |
| 10. Testing & Polish | 🟡 Medium | 4-5 |
| **Total** | | **29-39 hours** |

**Realistic estimate:** 35-40 hours (with debugging, iteration, etc.)

**Sprint breakdown:**
- **Sprint 1 (8-10h):** Phases 1-2, 5 (Foundation + Shell backend)
- **Sprint 2 (8-10h):** Phases 3-4 (Gating + Graph context)
- **Sprint 3 (8-10h):** Phases 6-7 (Orchestrator + CLI)
- **Sprint 4 (8-10h):** Phases 8-10 (Locks, Daemon, Polish)

---

## Success Metrics

**MVP (After Phase 7):**
- ✅ Can generate docs via CLI for single file
- ✅ SHA-based idempotence works
- ✅ RAG gating prevents stale docs
- ✅ Graph context included in prompts
- ✅ Shell backend functional

**Production Ready (After Phase 10):**
- ✅ Daemon auto-generates docs
- ✅ Concurrency control prevents conflicts
- ✅ All tests passing
- ✅ Documentation complete
- ✅ Example Gemini script works

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Graph context too large | High token costs | Add size limits, truncation |
| RAG gate too strict | Docs never generated | Make configurable, log clearly |
| Shell script failures | Silent failures | Timeout, validate output, log |
| Lock contention | Daemon stalls | Fail fast, clear messages |
| Gemini API costs | Budget overrun | Rate limiting, batch size control |

---

## Next Steps

1. **Review this plan** with team/self
2. **Start Phase 1** (Types & Config)
3. **Create feature branch:** `feature/docgen-v2`
4. **Track progress** in this document (check boxes)
5. **Update ROADMAP** as phases complete

---

## Progress Tracking

- [x] Phase 1: Types & Config ✅ **COMPLETE** (2025-12-03)
- [x] Phase 2: SHA Gating ✅ **COMPLETE** (2025-12-03)
- [x] Phase 3: RAG Gating ✅ **COMPLETE** (2025-12-03)
- [x] Phase 4: Graph Context ✅ **COMPLETE** (2025-12-03)
- [x] Phase 5: Shell Backend ✅ **COMPLETE** (2025-12-03)
- [x] Phase 6: Orchestrator ✅ **COMPLETE** (2025-12-03)
- [x] Phase 7: CLI Integration ✅ **COMPLETE** (2025-12-03)
- [x] Phase 8: Concurrency Control ✅ **COMPLETE** (2025-12-03)
- [ ] Phase 9: Daemon Integration (deferred)
- [ ] Phase 10: Testing & Polish

**Status:** MVP Complete - Phases 1-8 implemented and working!  
**Last updated:** 2025-12-03

**Notes:**
- Core docgen functionality is complete and working
- Phase 9 (Daemon integration) is deferred - can be added later when needed
- Phase 10 (Testing & Polish) - basic tests complete, can add more as needed
- Ready for production use via CLI: `llmc debug autodoc generate --all`


