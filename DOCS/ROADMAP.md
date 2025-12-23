# LLMC Roadmap

This roadmap focuses only on **active** work. Completed items are in `ROADMAP_COMPLETED.md`.

- **Now** – Current focus for work sessions
- **Next** – Post-launch improvements
- **Later** – Deeper refactors and R&D

---

## 1. Now (P0 / P1)

### 1.0 Case-Insensitive Symbol Resolution (P1) 🔥

**Status:** ✅ **COMPLETE** (2025-12-21)  
**Added:** 2025-12-21  
**Source:** LLMs constantly get casing wrong when using mcinspect, mcwho, etc.

**Problem:** All symbol lookups were case-sensitive. `mcinspect router` failed, but `mcinspect Router` worked.

**What was built:**
- Central `llmc/symbol_resolver.py` already existed with scored matching (exact > case-insensitive > suffix > contains)
- Added `resolve_symbol_in_nodes()` for rag_nav dict compatibility
- Migrated `llmc/rag_nav/tool_handlers.py` to use central resolver
- 20 unit tests (9 original + 11 new)

**All callers now use central resolver:**
- `llmc/rag/inspector.py` → `resolve_symbol_best()` ✅
- `llmc/mcwho.py` → `resolve_symbol()` ✅  
- `llmc/mcinspect.py` → via `inspect_entity()` ✅
- `llmc/rag_nav/tool_handlers.py` → `resolve_symbol_in_nodes()` ✅

**Effort:** ~30 minutes (architecture was already correct)

---

### 1.1 CLI Startup Performance (P1)

**Status:** ✅ **COMPLETE** (2025-12-21)  
**Added:** 2025-12-17

**Problem:** `llmc --help` takes several seconds due to eager imports of heavy ML libraries.

**Root Cause:** Top-level imports of `transformers`, `torch`, `sentence_transformers`, `sklearn`, `scipy`, `numpy`.

**Fix:** Move heavy imports inside command functions (lazy loading).

**What was built:**
- Lazy-load heavy imports in CLI commands (RAG/TUI) so `--help` is fast
- Lazy-load `sentence-transformers` model in `scripts/rag/index_workspace.py` (loads only when indexing, not for `--help`/`--stats`)

**Effort:** 4-6 hours | **Difficulty:** 🟢 Easy

---

### 1.2 File-Level Descriptions

**Status:** ✅ **COMPLETE** (2025-12-21)  
**Priority:** Medium  

Implemented file-level enrichment that generates ~50 word descriptions of each file's purpose.

**What was built:**
- `llmc debug file-descriptions` CLI command with `--mode cheap|rich` and `--force`
- Intelligent span prioritization: classes > modules > top-level functions
- Staleness tracking via `input_hash` - only recomputes when content changes
- `mcgrep` now shows real file descriptions, falls back to span proxy if none

**Run:** `llmc debug file-descriptions --force` to populate for existing repos.

**Effort:** ~4 hours | **Difficulty:** 🟢 Easy (simpler than estimated)

---

### 1.4 Context-Efficient Inspect (P1) 🔥

**Status:** ✅ **COMPLETE** (2025-12-21)  
**Added:** 2025-12-21  
**Source:** Codex feedback — `inspect --full` consumed 10% of context window for a "what is this repo" question

**Problem:** Current `mcinspect --full` dumps entire file contents. For quick orientation questions, most of that context is noise.

**What was built:**

1. **Default is now summary mode** — ~50 tokens:
   - Symbol name + kind + file path + line range
   - Enrichment summary
   - Callers/Callees from graph
   - Line count + byte size

2. **`--capsule` flag** — Ultra-compact 5-10 line output:
   - Purpose (file description)
   - Key exports (top 3 symbols)
   - Dependencies (top 3 callers)

3. **`--full` flag** — Preserved original behavior for when code dump is needed

**Example Output:**
```
EnrichmentPipeline (class, llmc/rag/enrichment_pipeline.py:155-716)
'Orchestrates batch enrichment with modular, testable design...'
Called by: service.run, workers.execute_enrichment, daemon.idle_loop
Calls: Database.write_enrichment, OllamaBackend.generate, RouterChain.select
Size: 716 lines, 24.2KB
```

**Also fixed:** CLI patterns for `mcinspect` and `mcread` (now work without subcommands).

**Effort:** ~2 hours (Jules implementation + fixes) | **Difficulty:** 🟢 Easy

---

### 1.3 Security Polish (P2)

**Remaining from 2025-12-17 audit:**

| Priority | Issue | Location | Risk |
|----------|-------|----------|------|
| **P2** | `os.chdir()` in RAG tools | `llmc_mcp/tools/rag.py` | MEDIUM - race conditions |
| **P2** | Unvalidated `repo_root` in RAG | `llmc_mcp/tools/rag.py` | MEDIUM - no `allowed_roots` check |

**📄 Full Report:** `tests/REPORTS/current/rem_mcp_2025-12-17.md`

---

## 2. Next (P1)

Things that make LLMC nicer to live with.

### 2.1 Integrated Graph-Enriched Search

**Status:** 🟡 Planned  
**Added:** 2025-12-19

**Goal:** Elevate rich schema-backed search from `llmc-rag-nav` into `llmc analytics search`.

**Current State:**
- `llmc analytics search` (vector-only) returns paths and snippets without context
- `llmc-rag-nav search` (hidden gem) provides AI summaries, usage examples, type metadata

**The Plan:**
1. Unify search to use `nav_search` logic when graph is available
2. Schema 3.0: Normalize edge semantics, add evidence (file:line), importance ranking
3. UX: `--rich/--plain` toggle

**Effort:** 6-8 hours | **Difficulty:** 🟢 Easy

---

### 2.2 Thin CLI Wrappers for MCP Tools (P1) 🎯

**Status:** ✅ **COMPLETE** (2025-12-21)  
**Added:** 2025-12-19

**Goal:** Create dead-simple CLI wrappers for MCP tools, enriched with schema graph data where useful.

**The Bigger Picture:**
These CLIs serve *two* purposes:
1. **Human/LLM UX:** Simple tools for common tasks
2. **Training Data:** OpenAI-format tool calling patterns for fine-tuning local models

```
mc* CLI Input/Output  →  OpenAI Tool Schemas  →  LLM Training Data
```

Each CLI is a *demonstration* of correct tool usage. Run `mcgrep "router"` → generates an example of `{"name": "rag_search", "arguments": {"query": "router"}}` with expected output. This becomes training data for teaching models how to use LLMC tools natively.

**The Pattern:**
| CLI | MCP Tool | OpenAI Schema | Status |
|-----|----------|---------------|--------|
| `mcgrep` | `rag_search` | `{"name": "rag_search", ...}` | ✅ DONE |
| `mcwho` | `rag_where_used` | `{"name": "rag_where_used", ...}` | ✅ DONE |
| `mcschema` | (orientation) | N/A | ✅ DONE |
| `mcinspect` | `inspect` | `{"name": "inspect", ...}` | ✅ DONE (2025-12-21) |
| `mcread` | `read_file` | `{"name": "read_file", ...}` | ✅ DONE (2025-12-21) |
| `mcrun` | `run_cmd` | `{"name": "run_cmd", ...}` | ✅ DONE (2025-12-21) |

**Graph Enrichment:**
| Tool | Enhancement |
|------|-------------|
| `mcread` | "Related: 3 callers, 5 imports" header | ✅ Implemented |
| `mcinspect` | Graph neighbor hints (callers/callees) | ✅ Implemented |
| `list_dir` | Connectivity ranking | 🟡 Planned |

**Training Data Generation:**
- [x] `--emit-training` flag on: `mcgrep`, `mcinspect`, `mcread`, `mcrun`
- [x] OpenAI-compatible JSON output format
- [x] Includes tool schemas for fine-tuning
- [ ] Collect corpus of tool usage patterns across repos (future)
- [ ] Fine-tune local models (Qwen, Llama) on LLMC-specific tool calling (future)

**Why This Matters:**
- No MCP required - models learn tool patterns directly
- Training data is generated from *actual* LLMC usage
- Graph enrichment teaches models to chain tools intelligently
- Fine-tuned models > prompt engineering for tool usage

**What was built:**
1. All mc* CLIs complete with graph enrichment
2. `llmc/training_data.py` - shared module for training data generation
3. `--emit-training` flag on mcgrep, mcinspect, mcread, mcrun

**Effort:** 12-16 hours (CLIs) + 8-12 hours (training emit) | **Difficulty:** 🟢 Easy → 🟡 Medium

**📄 Reference:** `llmc/mcgrep.py`, `llmc/mcwho.py` for patterns

---

### 2.3 AGENTS.md: OpenAI Tool Calling Convention (P1)

**Status:** 🔴 Blocked (depends on 2.2)  
**Added:** 2025-12-19

**Goal:** Update AGENTS.md to tell LLMs to use OpenAI-standard tool calling with the `mc*` CLIs.

**The Insight:**
LLMs have been trained *relentlessly* on OpenAI function calling format. If LLMC tools follow that format:
- **Zero learning curve** - models already know the pattern
- **Minimal context** - no need to dump 10KB of tool schemas
- **Same training pattern** works for MCP, CLI, or fine-tuning

**Before (Expensive):**
```markdown
## Tools
Here are 30 tools with their schemas...
[10KB of JSON definitions]
```

**After (Cheap):**
```markdown
## Tools
Use OpenAI-standard tool calling. Available locally:
- `mcgrep <query>` - semantic code search (rag_search)
- `mcwho <symbol>` - find callers/callees (rag_where_used)
- `mcread <file>` - read file with graph context (read_file)
```

**Why This Works:**
1. Models know `{"name": "...", "arguments": {...}}` format from training
2. Just tell them the tool names → they infer the schema
3. Graph-enriched outputs teach correct tool chaining
4. **Same instructions work for MCP, CLI, or local execution**

**Prerequisite:** Section 2.2 must be complete first (need the CLIs to exist)

**Changes to AGENTS.md:**
- Add section: "OpenAI Tool Calling Convention"
- List `mc*` tools with their MCP equivalents
- Remove verbose schema dumps
- Keep RAG-first contract, but simplify tool docs

**Effort:** 2-4 hours | **Difficulty:** 🟢 Easy (just docs)

---

### 2.4 RMTA Phase 2+ (P2)

Automated MCP testing orchestrator. Phase 1 (shell harness) is complete.

**Remaining:**
- [ ] Phase 2: Automated orchestrator (`llmc test-mcp --mode ruthless`)
- [ ] Phase 3: CI integration with quality gates
- [ ] Phase 4: Historical tracking and regression detection

---

### 2.5 Onboarding Polish (P2)

**Status:** ✅ **COMPLETE** (2025-12-21)

**What was built:**
- [x] Auto-run validation after `repo register`
- [x] Integration with `rag doctor` (embedding checks in health report)
- [x] Embedding model availability check (`check_embedding_models()`)
- [x] Helpful suggestions when models missing: `ollama pull model-name`
- [x] Non-blocking: warnings only, doesn't fail registration

---

### 2.6 PDF Sidecar System (P1) 📄

**Status:** ✅ **COMPLETE** (2025-12-21)  
**Added:** 2025-12-21  
**Source:** Reddit thread on RAG failures with PDFs  
**SDD:** `DOCS/planning/SDD_Document_Sidecar_System.md`

**The Problem:**
Everyone is trying to chunk PDFs directly and getting garbage:
- PDF parsing loses structure (tables, headings, columns)
- Chunking splits semantic units arbitrarily  
- Embeddings on PDF text produce noisy matches
- Users report "it couldn't find a topic that's clearly in the PDF"

**What was built:**

1. **Core Infrastructure (`llmc/rag/sidecar.py`):**
   - `SidecarConverter` class with pluggable converters
   - `PdfToMarkdown` (pymupdf), `DocxToMarkdown`, `PptxToMarkdown`, `RtfToMarkdown`
   - Freshness checking (`is_sidecar_stale`)
   - Orphan cleanup (`cleanup_orphan_sidecars`)

2. **Indexer Integration:**
   - `_iter_directory()` now yields sidecar-eligible files (PDF/DOCX)
   - `index_repo()` and `sync_paths()` generate sidecars automatically
   - `sidecar_path` column in files table for tracking

3. **CLI Commands (`llmc rag sidecar`):**
   - `list` - Show all sidecars + freshness status
   - `clean` - Remove orphaned sidecars
   - `generate` - Force regenerate sidecars for a path

4. **Tool Integration:**
   - `mcread` is sidecar-aware (reads markdown for PDFs transparently)
   - `mcgrep` shows 📄 indicator for files with sidecars

5. **Embedding Geometry Fix:**
   - File path and symbol now included in embedding text
   - Fixes "can't find PDF by title" issue

**Usage:**
```bash
llmc rag sidecar list           # Show all sidecars + freshness
llmc rag sidecar clean          # Remove orphans
llmc rag sidecar generate path/ # Force regenerate
mcread docs/spec.pdf            # Reads sidecar markdown transparently
```

**Effort:** ~12 hours | **Difficulty:** 🟡 Medium

---

### 2.9 Observability & Logging Hygiene (P2) 🔍

**Status:** 🟡 Planned  
**Added:** 2025-12-23  
**Source:** Architect Audit #5

**Problem:** 197 `print()` calls scattered across `llmc/rag/`. This is not a logging system - it's a teenager's diary scrawled on the bathroom wall.

**The Evidence:**
- `llmc/rag/database.py`: `print(f"Error loading enrichment DB: {e}")` → Lost when run as background service
- `llmc/rag/schema.py`: `print(f"Parse error...")` → Should be `logger.error()`
- `llmc/rag/service.py`: Carnival of prints: `print("🚀 RAG service started...")`
- No separation between user-facing CLI output and system logs

**The Prescription:**
1. **Banish print():** Every `print()` in `llmc/rag/` (except CLI entry points) → `logger.info/warning/error()`
2. **Centralize Configuration:** Use `logging.yaml` or `dictConfig` in `llmc/rag_daemon/logging_utils.py`
3. **UI/Log Separation:**
   - User-facing messages (CLI) → `rich.console.Console().print()`
   - System events (service) → `logging` to file/syslog
   - Never mix them

**Files to Audit:**
| File | print() Count | Priority |
|------|---------------|----------|
| `llmc/rag/service.py` | ~40 | HIGH |
| `llmc/rag/runner.py` | ~15 | MEDIUM |
| `llmc/rag/database.py` | ~10 | MEDIUM |
| `llmc/rag/schema.py` | ~8 | LOW |

**Effort:** ~4-6 hours | **Difficulty:** 🟢 Easy (mechanical refactor)

---

## 3. Later (R&D)

### 3.1 RAG Scoring System 3.0 🔥

**Status:** ✅ **COMPLETE** (2025-12-20)  
**Added:** 2025-12-19

**Problem:** Semantic search for implementation queries returns docs before code.

**What was built:**

All 4 phases implemented and merged via Dialectical Autocoding:

| Phase | Focus | Status |
|-------|-------|--------|
| **1** | RRF Fusion + Code@k Metric | ✅ Complete |
| **2** | Graph Neighbor Expansion | ✅ Complete |
| **3** | Z-Score Fusion + SetFit Router | ✅ Complete |
| **4** | LLM Setwise Reranking | ✅ Complete |

**📄 Full SDD:** `DOCS/planning/SDD_RAG_Scoring_System_3.0.md`

**Research Basis:** 285KB of academic literature synthesized from RepoGraph (ICLR 2025), RANGER, SetFit, Pinecone Hybrid Search studies.

---

### 3.2 Event-Driven Enrichment Queue (P1) 🔥

**Status:** 🟡 SDD Complete  
**Added:** 2025-12-21  
**SDD:** `DOCS/planning/SDD_Event_Driven_Enrichment_Queue.md`  
**Prerequisite for:** 3.3 Distributed Parallel Enrichment

**Problem:** Enrichment daemon polls ALL registered repos every 60s, even when 19/20 have zero pending work. Massive waste of CPU, prevents multi-worker scaling.

**Solution:** Central work queue with event-driven wake-up:
- Indexer pushes to queue when spans created
- Workers block on notification pipe (zero CPU when idle)
- Multiple workers pull from same queue (trivial parallelism)

**Phases:**
| Phase | Description | Difficulty | Effort |
|-------|-------------|------------|--------|
| 0 | Central Work Queue (SQLite) | 🟢 Easy | 4-6h |
| 1 | Indexer Integration (push on create) | 🟢 Easy | 2-3h |
| 2 | Event Notification (pipe/signal) | 🟡 Medium | 3-4h |
| 3 | Worker Refactor (queue consumers) | 🟡 Medium | 4-6h |
| 4 | Multi-Worker Support | 🟢 Easy | 2-3h |
| 5 | Remote Workers (HTTP API) | 🟡 Medium | 6-8h |

**Success Metrics:**
- Idle CPU: 15% → <1%
- Work discovery: 60s → <2s  
- Throughput: 1x → Nx (N workers)

**Total Effort:** 22-30 hours | **Difficulty:** 🟡 Medium

---

### 3.3 Distributed Parallel Enrichment

**Status:** 🔴 Blocked (depends on 3.2)

**Problem:** Single-host, synchronous enrichment underutilizes multi-GPU homelab.

**Architecture:**
```
         ┌──────────────────────────────────────┐
         │       ENRICHMENT DISPATCHER          │
         │   (async queue, work stealing)       │
         └──────────────┬───────────────────────┘
                        │
      ┌─────────────────┼─────────────────┐
      ▼                 ▼                 ▼
 [Athena:11434]   [Desktop:11434]   [Laptop:11434]
  (3 concurrent)   (1 concurrent)    (1 concurrent)
```

**Note:** Phase 4+5 of 3.2 (Event-Driven Queue) implements most of this. Once the queue exists, adding remote workers is straightforward.

**Remaining after 3.2:**
- Multiple Ollama backends per worker
- GPU load balancing
- Per-host concurrency tuning

**Additional Effort:** 8-12 hours (on top of 3.2) | **Difficulty:** 🟢 Easy (with queue in place)

---

### 3.4 Chat Session RAG

**Idea:** Use LLMC's chunking/embedding pipeline for past conversations.
- Semantic search: "That conversation where we discussed X"
- Inject context from past sessions into bx agent

**Why Later:** Core code RAG still has priority. Nice to have.

---

### 3.5 Configurable Tool Calling Format

**Context:** LLMC uses OpenAI format (industry standard), but Anthropic's XML format is cleaner.

**Goal:** Make format configurable per-profile:
```toml
[profiles.boxxie]
tool_format = "openai"  # Default

[profiles.claude-agent]
tool_format = "anthropic"  # XML-based
```

**Effort:** 8-12 hours | **Difficulty:** 🟢 Easy

---

## 4. How to Use This Roadmap

- Start a work session → pick ONE item from **Now**
- When something is truly done → move to `ROADMAP_COMPLETED.md`
- Periodically reshape **Next** and **Later** based on what's exciting

The goal is a **small, accurate map** of where LLMC is going from here.
