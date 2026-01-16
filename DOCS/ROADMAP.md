# LLMC Roadmap

This roadmap focuses only on **active** work. Completed items are in `ROADMAP_COMPLETED.md`.

- **Now** – Current focus for work sessions
- **Next** – Post-launch improvements
- **Later** – Deeper refactors and R&D

---

## 1. Now (P0 / P1)

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

**Status:** 🔴 Not Started  
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

### 2.13 Migrate to watchfiles for File Watching (P2) 👁️

**Status:** 🔴 Not Started  
**Added:** 2025-12-24  
**Source:** Architecture review - pyinotify is old and unmaintained

**Current State:**
- Using `pyinotify` in `llmc/rag/watcher.py`
- pyinotify is Linux-only, unmaintained since 2018
- Manual ThreadedNotifier setup, edge-case bugs

**The Solution:**
[watchfiles](https://github.com/samuelcolvin/watchfiles) (by Pydantic author):
- **Rust core** - 10-100x faster than Python-based watchers
- **Cross-platform** - Linux (inotify), macOS (FSEvents), Windows
- **Simple API** - no manual notifier setup
- **Already in deps** - just not wired in

```python
from watchfiles import watch

for changes in watch('/path/to/repo'):
    for change_type, path in changes:
        handle_change(change_type, path)
```

**What to build:**
1. Replace `RepoWatcher` internals with `watchfiles.watch()`
2. Remove pyinotify dependency
3. Update tests

**Benefits:**
- Faster file change detection
- Cross-platform (works on macOS for dev)
- Less code to maintain
- Active maintenance

**Effort:** 4-6 hours | **Difficulty:** 🟢 Easy

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
