# LLMC Roadmap

This roadmap focuses only on **active** work. Completed items are in `ROADMAP_COMPLETED.md`.

- **Now** – Current focus for work sessions
- **Next** – Post-launch improvements
- **Later** – Deeper refactors and R&D

---

## 1. Now (P0 / P1)

### 1.W RLM Phase 1: Callback Interception (P0) ✅
**Status:** ✅ **COMPLETE** (2026-01-24)
**Added:** 2026-01-24
**Source:** RLM Phase 1 Implementation Plan

**Problem:** `ProcessSandboxBackend` cannot support callbacks directly (runtime error).
**Solution:** AST-based interception in orchestrator.
- Rewrites `x = tool()` to use injected variables
- Supports `nav_*` tools with literal arguments
- Rejects invalid patterns (bare calls, nested calls) with helpful feedback

**Effort:** 2-4 hours | **Difficulty:** 🟡 Medium

### 1.0 Eliminate Hardcoded Model Defaults (P0) 🚨

**Status:** ✅ **COMPLETE** (2026-01-16)  
**Added:** 2026-01-15  
**Source:** RAG search failure due to wrong model being used; hardcoded `qwen2.5:7b` when config says `qwen3:4b-instruct`

**The Problem:**
Multiple files had hardcoded model names that override `llmc.toml` configuration.

**What was built:**
1. Created `llmc/rag/config_models.py` with `get_default_enrichment_model(repo_root)`:
   - Reads from `ENRICH_MODEL` env var (highest priority)
   - Falls back to `llmc.toml [enrichment].default_model`
   - Falls back to first enabled chain's model field
   - Final fallback constant only when no config available

2. Migrated all callers:
   - `service_health.py` → uses `get_default_enrichment_model()`
   - `file_descriptions.py` → uses `get_default_enrichment_model()`
   - `workers.py` → uses `get_default_enrichment_model()`
   - `cli.py` → uses `get_default_enrichment_model()`
   - `pool_config.py` → uses `get_default_enrichment_model()`

**Effort:** 2-3 hours | **Difficulty:** 🟢 Easy

---

### 1.0.1 Case-Insensitive Symbol Resolution (P1) 🔥

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

**Status:** ✅ **COMPLETE** (2025-12-23)  
**Added:** 2025-12-17  
**SDD:** `DOCS/planning/SDD_Security_Polish.md`

**What was fixed (PR #60 - Jules):**

| Priority | Issue | Fix |
|----------|-------|-----|
| **P2** | `os.chdir()` in RAG tools | ✅ Removed all `os.chdir()` from `llmc_mcp/tools/rag.py` |
| **P2** | Unvalidated `repo_root` in RAG | ✅ Added `validate_repo_root()` with `allowed_roots` check |

**Tests:**
- `tests/security/test_rag_security.py` - 4 tests for `validate_repo_root()`
- `tests/mcp/test_fs_security.py` - 3 tests for path traversal + symlink escape

**📄 Full Report:** `tests/REPORTS/current/rem_mcp_2025-12-17.md`

---

## 2. Next (P1)

Things that make LLMC nicer to live with.

### 2.1 Integrated Graph-Enriched Search

**Status:** ✅ **COMPLETE** (2025-12-23)  
**Added:** 2025-12-19

**What was built:**
- `llmc search` as top-level entry point (most discoverable)
- Uses FTS + reranker + 1-hop graph stitch when available
- Falls back to embedding search, then grep
- `--rich` / `--plain` / `--json` output modes
- Shows source info (`RAG_GRAPH` vs `LOCAL_FALLBACK`)
- Graph context (callers/callees) in rich output

**Files:**
- `llmc/commands/search.py` — Unified search module
- Updated `llmc/main.py` — Added `llmc search` command

**Effort:** ~2 hours (less than estimated) | **Difficulty:** 🟢 Easy

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

**Status:** ✅ **COMPLETE** (2025-12-23)  
**Added:** 2025-12-19

**Goal:** Update AGENTS.md to tell LLMs to use OpenAI-standard tool calling with the `mc*` CLIs.

**The Insight:**
LLMs have been trained *relentlessly* on OpenAI function calling format. If LLMC tools follow that format:
- **Zero learning curve** - models already know the pattern
- **Minimal context** - no need to dump 10KB of tool schemas
- **Same training pattern** works for MCP, CLI, or fine-tuning

**What was built:**
1. **Simplified Section 5 (RAG Tooling Reference):**
   - Replaced verbose flag tables with clean `mc*` CLI reference
   - Added `--emit-training` documentation for training data generation

2. **Added Section 5.5 (OpenAI Tool Calling Convention):**
   - Explains the paradigm shift (expensive schema dumps → cheap tool names)
   - MCP equivalents table mapping CLI → MCP → OpenAI format
   - "The Pattern" section showing models already know the format

3. **Deduplicated mc* CLI Reference:**
   - Section 7 now points to Section 5 as authoritative source
   - Consistent examples across the document

**Effort:** ~30 minutes | **Difficulty:** 🟢 Easy (just docs)

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

### 2.9 Observability & Logging Hygiene (P1) 🔍

**Status:** ✅ **COMPLETE** (2025-12-23)  
**Added:** 2025-12-23  
**Source:** Architect Audit #5  
**Audit Report:** `DOCS/operations/audits/05_OBSERVABILITY_LOGS.md`  
**SDD:** `DOCS/planning/SDD_Observability_Logging_Hardening.md`

**What was built:**
- `llmc/rag/enrichment_logger.py` — Thread-safe, atomic JSONL logger
- `EnrichmentLogger` class with `log_success()`, `log_failure()`, `log_batch_summary()`
- `repair_ledger()` function for corrupt ledger recovery
- `llmc debug repair-logs` CLI command
- `run_ledger.jsonl` as new atomic format
- Replaced print() with structured logging in daemon/enrichment
- `fcntl` locking for multi-process safety

---

### 2.10 Multi-Backend LLM Providers (P1) 🔌

**Status:** ✅ **Phase 1 COMPLETE** (2025-12-23)  
**Added:** 2025-12-23  
**Source:** Athena runs llama.cpp, other machines run Ollama. LLMC must be polyglot.

**The Problem:**
- Ollama has API quirks (different tool_calls format, Modelfile dance)
- llama.cpp server uses proper OpenAI-compatible API
- Different servers have different backends - need to work with all of them
- Homelab has: Athena (llama.cpp), Desktop (Ollama), Laptop (Ollama)

**What Was Built (Phase 1):**
1. **`OpenAICompatBackend`** (`llmc_agent/backends/openai_compat.py`):
   - Works with llama-server, vLLM, text-generation-inference, OpenAI
   - Full tool calling support via OpenAI API format
   - Proper `choices[0].message` parsing

2. **Config-Driven Provider Selection:**
   - `[agent] provider = "openai"` or `"ollama"`
   - `[openai]` section for llama-server config
   - Environment override: `LLMC_AGENT_PROVIDER=openai`

3. **UTP Parser Fix:**
   - `OpenAINativeParser` now handles both Ollama and OpenAI response formats
   - Properly extracts tool_calls from `choices[0].message.tool_calls`

**Usage:**
```bash
# Use llama-server (OpenAI-compatible)
LLMC_AGENT_PROVIDER=openai bx "your question"

# Or set permanently in llmc.toml:
[agent]
provider = "openai"
```

**Remaining (Phase 2+):**
- [ ] **KoboldCpp/llama.cpp compatibility** (2025-12-24)
  - Issue: `OpenAICompatBackend` parses wrong JSON from KoboldCpp responses
  - KoboldCpp returns valid responses but JSON extraction grabs schema, not output
  - Debug: compare raw response format between Ollama vs KoboldCpp
  - Fix: improve `_parse_enrichment_json()` or add KoboldCpp-specific adapter
- [ ] Per-profile provider selection (different profiles → different backends)
- [ ] Enrichment chain support for OpenAI-compatible backends
- [ ] Health check that tests ALL configured backends
- [ ] Auto-failover between backends
- [ ] vLLM-specific backend (tensor parallelism, continuous batching)

**Effort:** Phase 1: ~4 hours ✅ | Phase 2+: 8-12 hours | **Difficulty:** 🟡 Medium

---

### 2.11 Adopt litellm for Provider Abstraction (P1) 🔌

**Status:** ✅ **COMPLETE** (2026-01-13)  
**Added:** 2025-12-24  
**HLD:** `DOCS/design/HLD-litellm-migration-FINAL.md`  
**Source:** Architecture review - stop yak-shaving on provider adapters

**The Problem:**
- Every LLM provider has slightly different API, auth, error handling
- Currently writing custom adapters for Ollama, OpenAI, llama.cpp, KoboldCpp
- Each adapter is a maintenance burden and source of bugs
- ~1,700 lines of duplicated provider-specific code across 8 files

**Approved Architecture (from HLD-FINAL):**
- `LiteLLMAgentBackend` (async) — implements `Backend` ABC
- `LiteLLMEnrichmentAdapter` (sync) — implements `BackendAdapter` Protocol  
- `LiteLLMCore` — shared logic (config, exception mapping, JSON parsing)
- Feature-flag rollout with instant rollback capability

**Flagged Decisions (deferred to implementation):**
1. Add `generate_with_tools()` to Backend ABC? → Recommend YES
2. Streaming + tool calls test coverage level? → TBD
3. Health check optimization? → Keep simple for v1

**Migration Phases:**

| Phase | Tasks | Effort | Status |
|-------|-------|--------|--------|
| 1 | Foundation: split backends, core logic, tests | 6-8 hours | ✅ Complete |
| 2 | Feature Flag: wire into Agent + Factory | 3-4 hours | ✅ Complete |
| 3 | Validation: test all providers, streaming, tools | 4-6 hours | ✅ Complete |
| 4 | Cutover: flip flag, monitor | 1 hour | ✅ Complete |
| 5 | Cleanup: remove old code, docs | 3-4 hours | ✅ Complete |
| **Total** | | **18-25 hours** | |

**Implementation Progress (2026-01-13):**
- `llmc/backends/litellm_core.py` — Shared logic (LiteLLMConfig, LiteLLMCore)
- `llmc/backends/litellm_agent.py` — Async LiteLLMAgentBackend  
- `llmc/backends/litellm_enrichment.py` — Sync LiteLLMEnrichmentAdapter
- `llmc_agent/config.py` — Added LiteLLMConfig with feature flag
- `llmc_agent/agent.py` — Factory integration with `litellm.enabled` check
- `tests/agent/test_litellm_backends.py` — 29 unit tests
- `tests/agent/test_litellm_validation.py` — 31 validation tests (Phase 3)
- **Total: 66 tests passing** covering:
  - Ollama provider (tool_choice skip, model translation)
  - OpenAI provider (api_key, api_base, tool_choice=auto)
  - Streaming (chunks, empty handling, num_retries removal)
  - Tool calling (parsing, multiple calls, finish_reason)
  - Enrichment adapter (JSON parsing, circuit breaker, rate limiter)
  - Exception mapping (RateLimitError, Timeout, AuthenticationError)
- **Phase 4 Live Validation (2026-01-13):**
  - Health check: ✓ PASS
  - Basic generate: ✓ PASS (qwen3-next-80b-tools)
  - Streaming: ✓ PASS (9 chunks received)
  - Tool calling: ✓ PASS (search_code tool invoked)
  - Config: `llmc.toml` [litellm] section added
- **Phase 5 Cleanup (2026-01-13):**
  - LiteLLM enabled by default in config
  - `create_litellm_backend()` factory added to enrichment_factory.py
  - Old backends marked deprecated (kept for fallback)
  - 72 tests passing (66 agent + 6 enrichment)

**Benefits:**
- Tool calling normalization across providers
- Built-in retry/fallback logic
- Streaming support
- ~1,700 lines of provider code removed
- Community-maintained edge case handling

**Effort:** 18-25 hours | **Difficulty:** 🟡 Medium
---

### 2.12 Dependency Audit: Remove Dead Weight (P2) 🧹

**Status:** ✅ **COMPLETE** (2026-01-17)  
**Added:** 2025-12-24  
**Source:** Architecture review - deps listed but not imported

**The Problem:**
These dependencies are in `pyproject.toml` but have zero imports in codebase:
- `langchain` / `langgraph` — RAG framework, never used
- `chromadb` — vector store, never wired in
- `watchdog` / `watchfiles` — file watchers, not referenced

**Verification Commands:**
```bash
grep -r "import langchain\|from langchain" llmc/ llmc_mcp/ llmc_agent/
grep -r "import chromadb\|from chromadb" llmc/ llmc_mcp/ llmc_agent/
grep -r "import watchdog\|from watchdog" llmc/ llmc_mcp/ llmc_agent/
```

**Action:**
1. Run verification commands
2. If zero matches, remove from `pyproject.toml`
3. Document any that ARE used but just not visible in grep

**Effort:** 30 minutes | **Difficulty:** 🟢 Easy

---

### 2.13 Migrate to watchfiles for File Watching (P2) ✅

**Status:** ✅ **COMPLETE** (2026-01-17)  
**Added:** 2025-12-24  
**Source:** Architecture review - pyinotify is old and unmaintained  
**SDD:** `DOCS/planning/SDD_Watchfiles_Migration.md`

**What was built:**
- Replaced pyinotify with watchfiles in `llmc/rag/watcher.py`
- Added `LLMCFilter` extending `DefaultFilter` for gitignore-aware filtering
- Graceful fallback when watchfiles not installed
- Error handling in watcher thread to prevent silent death
- `time.monotonic()` for clock-safe debouncing

**Benefits:**
- Cross-platform (Linux, macOS, Windows)
- Rust core - 10-100x faster
- Simpler API - iterator-based
- Active maintenance (Pydantic author)

**Effort:** ~4 hours | **Difficulty:** 🟢 Easy

---

### 1.5 Schema Compliance & Integrity (P0) 🚨

**Status:** ✅ **COMPLETE** (2025-12-23)  
**Added:** 2025-12-23  
**Source:** Architect Audit #7  
**SDD:** `DOCS/planning/SDD_Schema_Migration_Health_Check.md`

**What was built:**
- `check_and_migrate_all_repos()` — validates/migrates all registered repos at startup
- `llmc debug schema-check [--migrate] [--json]` — CLI for manual validation
- Service startup now logs schema versions
- Eliminates "no column named X" crashes

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

**Status:** 🟡 Phases 0-4 Complete, Phase 5 Remaining  
**Added:** 2025-12-21  
**Updated:** 2025-12-23  
**SDD:** `DOCS/planning/SDD_Event_Driven_Enrichment_Queue.md`  
**Prerequisite for:** 3.3 Distributed Parallel Enrichment

**What was built:**
- `llmc/rag/work_queue.py` — Central queue (772 lines): push/pull/complete/fail/heartbeat/orphan recovery
- `llmc/rag/pool_worker.py` — Backend-bound worker (582 lines): pulls from queue, calls Ollama directly
- `llmc/rag/pool_manager.py` — Spawns/monitors multiple workers (381 lines): scheduling, health checks
- Named pipe notification with `wait_for_work()` using select()
- `feed_queue_from_repos()` for indexer integration

**Phases:**
| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Central Work Queue (SQLite) | ✅ Complete |
| 1 | Indexer Integration (push on create) | ✅ Complete |
| 2 | Event Notification (pipe/signal) | ✅ Complete |
| 3 | Worker Refactor (queue consumers) | ✅ Complete |
| 4 | Multi-Worker Support | ✅ Complete |
| 5 | Remote Workers (HTTP API) | 🔴 Not Started |

**Known Issues (2025-12-23):**
- SQLite locking with multiple workers hitting `work_queue.db`
- FIFO pipe creation unreliable across daemon restarts
- **Workaround:** KISS mode (single-process async) as stable baseline

**Remaining:** Phase 5 (HTTP API) would eliminate SQLite locking for distributed workers

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

### 1.X RLM Configuration Surface Implementation (P0) 🚨

**Status:** ✅ **COMPLETE**  
**Added:** 2026-01-24  
**Completed:** 2026-01-25  
**Commit:** 6c330e8 (feat/rlm-config-nested-phase-1x)  
**Source:** Oracle code review of RLM Phase 1.1.1 implementation

**Implementation Summary:**

Implemented comprehensive nested TOML configuration for RLM with full backward compatibility. Users can now configure RLM via nested `[rlm.*]` sections in `llmc.toml`.

**What Was Delivered:**

1. ✅ **Nested TOML Parsing** (`llmc/rlm/config.py`)
   - Completely rewrote `_parse_rlm_section()` to parse all nested sections
   - Handles: budget, sandbox, llm.root/sub, token_estimate, session, trace
   - Supports alias mapping (canonical vs legacy names)
   - Full type validation with clear error messages

2. ✅ **CLI Integration** (`llmc/commands/rlm.py`)
   - Updated CLI to call `load_rlm_config()` by default
   - Loads from `llmc.toml` with CLI overrides still working
   - Users can configure via file instead of hardcoded defaults

3. ✅ **Core Wiring**
   - session.py: Uses all config fields
   - sandbox/*: Fully wired (backend, security_mode, timeouts, builtins, modules)
   - budget.py: Integrated
   - nav: Wired to config

4. ✅ **Comprehensive Testing**
   - Added 6 nested parsing tests (13 total, was 7)
   - Test fixtures: minimal, permissive, restrictive TOMLs
   - All tests pass: 42 RLM tests (2 skipped)
   - Integration verified end-to-end

5. ✅ **Complete Documentation** (`DOCS/reference/config/rlm.md`)
   - 267-line reference guide
   - Migration notes with backward compatibility details
   - Examples for all use cases
   - Config inventory documenting 29 configurable values

**TOML Schema Implemented:**

```toml
[rlm]
root_model = "ollama_chat/qwen3-next-80b"
sub_model = "ollama_chat/qwen3-next-80b"

[rlm.budget]
max_session_budget_usd = 1.00
max_session_tokens = 500_000
soft_limit_percentage = 0.80
max_subcall_depth = 5

[rlm.sandbox]
backend = "process"
security_mode = "permissive"  # or "restrictive"
code_timeout_seconds = 30
max_output_chars = 10_000
blocked_builtins = ["open", "exec", "eval", ...]
allowed_modules = ["json", "re", "math", ...]

[rlm.llm.root]
temperature = 0.1
max_tokens = 4096

[rlm.llm.sub]
temperature = 0.1
max_tokens = 1024

[rlm.token_estimate]
chars_per_token = 4
safety_multiplier = 1.2

[rlm.session]
max_turns = 20
session_timeout_seconds = 300
max_context_chars = 1_000_000

[rlm.trace]
enabled = true
prompt_preview_chars = 200
response_preview_chars = 200
stdout_preview_chars = 2000

[rlm.pricing]  # Note: Pricing stays at [rlm.pricing], not nested under budget
default = { input = 0.01, output = 0.03 }
"ollama_chat/qwen3-next-80b" = { input = 0.0, output = 0.0 }
```

**Backward Compatibility:**
- ✅ Legacy flat keys still work (no breaking changes)
- ✅ Nested keys take precedence when both present
- ✅ All existing code continues to work
- ✅ No deprecation warnings yet (planned for Phase 1.X.1)

**Acceptance Criteria Met:**
- ✅ `load_rlm_config()` reads from `llmc.toml`
- ✅ 29 configurable values surfaced (critical + high priority items)
- ✅ Backward compatibility: missing config = current defaults
- ✅ Type validation with helpful error messages
- ✅ Full config reference documentation
- ✅ Example TOMLs in tests/fixtures/

**Files Changed:** 41 files (+4131/-61 lines)
- Core: config.py, commands/rlm.py, session.py, sandbox/*, budget.py, nav/*
- Tests: test_config.py (+6 tests), 3 fixture TOMLs
- Docs: DOCS/reference/config/rlm.md (267 lines)

**Branch:** feat/rlm-config-nested-phase-1x  
**PR:** Ready for review  
**Tests:** ✅ 13 config tests, 42 total RLM tests (all passing)

**Deferred to Phase 1.X.1:**
- Deprecation warnings for legacy aliases
- Full nested dataclass views (pragmatic flat approach used)
- Remaining low-priority template strings

**Reference:**
- Completion report: `.sisyphus/notepads/rlm-config-surface-phase-1x/COMPLETE.md`
- Config inventory: `.sisyphus/notepads/rlm-config-surface-phase-1x/inventory.md`
- Implementation notes: `.sisyphus/notepads/rlm-config-surface-phase-1x/implementation.md`

### 1.Y RLM Phase 1.1.1 Bug Fixes (P0) 🐛

**Status:** ✅ **COMPLETE**  
**Completed:** 2026-01-25  
**Added:** 2026-01-24  
**Source:** Implementation session - feature branch needs cleanup before merge  
**Branch:** `feat/rlm-config-nested-phase-1x` (worked on current branch instead of feature/rlm-phase-1.1.1)  

**Completion Summary:**
- ✅ 43/43 RLM tests passing (100%)
- ✅ urllib3 dependency conflict resolved
- ✅ DeepSeek integration working with real API
- ✅ Budget tracking verified
- ✅ All known issues fixed

**Issues Resolved:**

1. **TreeSitterNav Class Symbol Extraction** ✅
   - Status: ALREADY FIXED (test was passing, roadmap was stale)
   - Test `tests/rlm/test_nav.py::test_ls_filters_by_scope` passes

2. **Venv litellm Installation Conflict** ✅ FIXED
   - **Solution:** Changed `pyproject.toml` line 12 from `urllib3>=2.6.0` to `urllib3>=1.24.2,<2.4.0`
   - **Result:** urllib3 downgraded from 2.6.3 to 2.3.0, compatible with kubernetes 34.1.0
   - **Verification:** litellm 1.80.16 now imports successfully

3. **Session Live API Validation** ✅ COMPLETE
   - **Tests:** Both integration tests in `tests/rlm/test_integration_deepseek.py` passing
   - **Test 1:** `test_rlm_deepseek_code_analysis` - Full session loop working
   - **Test 2:** `test_rlm_deepseek_budget_enforcement` - Budget limits enforced
   - **Note:** Tests require `--allow-network` flag due to pytest_ruthless plugin

**Test Results:**
- Baseline: 41 passed, 2 skipped (litellm missing)
- After fix: 43 passed, 0 skipped
- Command: `pytest tests/rlm/ -v --allow-network`

**Files Modified:**
- `pyproject.toml` - Fixed urllib3 constraint

**Acceptance Criteria:** ✅ ALL MET
- ✅ All 43/43 tests passing
- ✅ Live DeepSeek integration test passes
- ✅ Budget tracking verified with real API
- ✅ Session completes full loop with FINAL() answer
- ✅ Ready to merge to main

**Completion Date:** 2026-01-25  
**Actual Effort:** 1 hour | **Difficulty:** 🟢 Easy  

---

### 1.Z RLM Phase 1.2 - MCP Tool Integration (P1)

**Status:** 📋 **PLANNED**  
**Added:** 2026-01-24  
**Source:** SDD_RLM_Integration_Phase1.1.1.md - Phase 1.2 entry points  
**Depends On:** 1.Y (bug fixes)

**What Needs To Be Built:**

1. **MCP Tool Wrapper (`llmc_mcp/tools/rlm.py`)**
   - Expose RLMSession via MCP protocol
   - Tool signature:
     ```python
     async def rlm_query(
         task: str,
         file_path: str | None = None,
         context: str | None = None,
         budget_usd: float = 1.00,
     ) -> dict
     ```
   - Returns structured response with answer + budget summary
   - Error handling for budget exceeded, timeout, etc.

2. **MCP Server Registration**
   - Add to `llmc_mcp/server.py` tool registry
   - Schema generation for Claude/other MCP clients
   - Documentation in tool description

3. **Integration Tests**
   - `tests/mcp/test_rlm_tool.py`
   - Mock LLM backend for deterministic tests
   - Budget enforcement verification
   - Error handling tests

**Acceptance Criteria:**
- ✅ `rlm_query` tool registered in MCP server
- ✅ Works via `llmc-mcp` stdio protocol
- ✅ Claude can invoke RLM analysis
- ✅ Integration tests passing
- ✅ Documented in MCP tool list

**Effort:** 3-4 hours | **Difficulty:** 🟢 Easy  
**Reference:** SDD Section 6.3 (MCP Integration)

---

### 1.AA RLM Phase 1.3 - Documentation & Examples (P2)

**Status:** 📋 **PLANNED**  
**Added:** 2026-01-24  
**Source:** Implementation - needs user-facing docs  
**Depends On:** 1.Y (bug fixes), 1.Z (MCP tool)

**What Needs To Be Built:**

1. **User Guide (`DOCS/guides/RLM_User_Guide.md`)**
   - What is RLM? (Recursive Language Model for code analysis)
   - When to use it vs regular RAG search
   - CLI examples with real scenarios
   - Budget management tips
   - Troubleshooting common issues

2. **Architecture Documentation (`DOCS/architecture/RLM_Architecture.md`)**
   - Component overview (sandbox, budget, navigation, session)
   - Flow diagrams (session loop, budget enforcement)
   - Design decisions and trade-offs
   - V1.1.0 → V1.1.1 fixes explained

3. **API Reference (`DOCS/reference/RLM_API.md`)**
   - CLI command reference
   - MCP tool signature
   - Configuration options (once 1.X config surface is done)
   - Python API for programmatic use

4. **Example Scenarios**
   - "Analyze performance bottlenecks in this file"
   - "Find all usages of this function and explain"
   - "Generate test cases for this module"
   - Budget-constrained analysis

**Acceptance Criteria:**
- ✅ User guide with 5+ real examples
- ✅ Architecture doc with diagrams
- ✅ API reference complete
- ✅ Examples tested and working
- ✅ Linked from main LLMC docs

**Effort:** 4-6 hours | **Difficulty:** 🟢 Easy  
**Reference:** SDD_RLM_Integration_Phase1.1.1.md

---

### 1.AB RLM Phase 2 - Advanced Features (P3 - Future)

**Status:** 📋 **DEFERRED**  
**Added:** 2026-01-24  
**Source:** SDD_RLM_Integration_Phase1.1.1.md - Phase 2+ roadmap

**Future Enhancements (Post-MVP):**

1. **RestrictedPython Sandbox Backend (Tier -1)**
   - More restrictive than process backend
   - For untrusted contexts
   - No subprocess spawning allowed

2. **Multi-File Context Loading**
   - Load entire directory as context
   - Cross-file navigation
   - Workspace-level analysis

3. **Streaming Response Support**
   - Stream intermediate findings back to user
   - Real-time budget updates
   - Cancellable long-running sessions

4. **Sub-Call Result Caching**
   - Cache llm_query() results by prompt hash
   - Reduce redundant API calls
   - TTL-based invalidation

5. **Advanced Navigation Tools**
   - AST-based queries (not just regex)
   - Call graph traversal
   - Data flow analysis

6. **Multi-Modal Support**
   - Analyze diagrams, screenshots alongside code
   - PDF/document context integration
   - Image-based debugging

7. **IPC Callbacks (Process Backend)**
   - Full callback support via IPC (multiprocessing.Queue)
   - Allows nested calls, complex args, `llm_query()` from inside sandbox
   - Replaces Phase 1 AST interception

**Effort:** TBD | **Difficulty:** 🔴 Hard  
**Reference:** SDD Section 9 (Future Work)

---

## 5. Someday Maybe (Research)

### 5.1 LSP Graph Integration 🔬

**Status:** 📋 **RESEARCH BACKLOG**  
**Added:** 2026-01-25  
**Source:** Architecture discussion - could LSP enrich LLMC's graph beyond Tree-sitter?

**The Question:**
Tree-sitter provides fast, offline AST parsing but is **syntactic only**. Could integrating with LSP servers (pyright, typescript-language-server) add semantic value to the graph?

**What LSP Could Add:**
| Capability | Tree-sitter (Current) | LSP (Potential) |
|------------|----------------------|-----------------|
| Cross-file references | ❌ No | ✅ "This calls function in file B" |
| Type information | ❌ No | ✅ "Variable x is `List[CodeBlock]`" |
| Import resolution | ❌ Syntax only | ✅ Trace actual module paths |
| Semantic symbols | ❌ No | ✅ "Method override" vs "method" |

**Trade-offs:**
- ✅ Rich semantic data for better context stitching
- ❌ Requires running server per language
- ❌ Slower than Tree-sitter for bulk indexing
- ❌ Flaky with broken/incomplete code

**Hybrid Strategy (Hypothesis):**
1. **Index** with Tree-sitter (fast, offline, robust)
2. **Enrich on-demand** via LSP for semantic queries (find-references, type info)

**Research Spike:**
- [ ] Prototype pyright integration for Python repos
- [ ] Compare `nav_where_used` with LSP `textDocument/references`
- [ ] Measure latency + accuracy delta
- [ ] Evaluate graph enrichment value vs complexity

**Effort:** TBD (research spike: 4-8 hours) | **Difficulty:** 🔴 TBD  
**Related:** oh-my-opencode's LSP tools (`lsp_goto_definition`, `lsp_find_references`)

---
