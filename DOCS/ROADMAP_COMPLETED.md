# LLMC Roadmap - Completed Items

Archive of completed roadmap items, moved from `ROADMAP.md` when done.

---

## December 2025

### 2025-12-19

- **RAG Doctor: Pending Embeddings Lie Fixed**
  - Doctor was reporting 5171 pending embeddings when worker said 0
  - Root cause: Doctor only checked `embeddings` table, not `emb_code`
  - Fix: Updated query to match worker logic

- **Markdown 0-Spans Migration Bug Fixed**
  - Files indexed before TechDocsExtractor integration had 0 spans
  - Fix: Auto-migration in indexer detects and re-extracts

- **mcgrep CODE/DOCS Separation**
  - Output now shows `── CODE ──` (top 20) and `── DOCS ──` (top 5) sections

### 2025-12-18/19

- **Native Ollama/OpenAI Tool Calling Format (P0)**
  - Unified Tool Protocol (UTP) implementation
  - `llmc_agent/format/` package with multi-format parsers
  - `OpenAINativeParser`, `XMLToolParser`, `CompositeParser`
  - `FormatNegotiator` factory for parser selection
  - 22 unit tests
  - Default model → `qwen3-next-80b-tools`
  - Fixed native tool detection, argument encoding, synthesis loop

### 2025-12-17

- **Security Hardening (P0) - All items complete**
  - RCE in `execute_code` - fixed (subprocess isolation)
  - SSRF in `service_health` - fixed (URL validation)
  - 8 dependency CVEs updated
  - `linux_proc_*` gated behind `require_isolation()`
  - `te_run` RCE via env var - fixed
  - `is_isolated_environment` false positive - fixed
  - Isolation bypass audit logging added

- **Domain RAG - Technical Documentation Support (P0)**
  - All 5 phases complete
  - `TechDocsExtractor` for heading-aware chunking
  - Tech docs enrichment prompts
  - Graph edges: REFERENCES, REQUIRES, WARNS_ABOUT
  - CI smoke tests on LLMC's own DOCS/
  - 📄 Design: `legacy/SDD_Domain_RAG_Tech_Docs.md`

### 2025-12-16

- **Architecture Polish & Tech Debt**
  - Renamed `graph.py` → `graph_store.py` (fixed import cycle)
  - Deferred heavy imports in `llmc/commands/docs.py`
  - Created `llmc/security.py` with shared path utilities
  - Added dev dependencies to pyproject.toml
  - Created `DOCS/ARCHITECTURE.md`

- **MCP Hybrid Mode (v0.7.0 "Trust Issues")**
  - New `mode = "hybrid"` for trusted MCP clients
  - ~76% token reduction vs classic mode
  - Simplified run_cmd security model
  - 📄 SDD: `planning/SDD_MCP_Hybrid_Mode.md`

### 2025-12-14

- **Idle Enrichment**
  - Daemon runs enrichment during idle periods
  - DeepSeek as OpenAI-compatible provider
  - Cost control with `max_daily_cost_usd`

- **Silent Extractor Failure Fix (VULN-RAG-001)**
  - `replace_spans()` now preserves existing spans when new list is empty
  - 412 spans recovered from 111 affected files

### 2025-12-13

- **TechDocsExtractor Integration**
  - Heading-aware chunking with hierarchical section paths
  - Size ceiling (2500 chars) with paragraph-based splitting
  - README.md: 195 spans → 9 coherent chunks

- **MCP Write Tools Actually Exposed (AAR-MCP-001)**
  - Root cause: code_execution mode was filtering tools
  - Fix: Use classic mode with full 23 tools

### 2025-12-12

- **Command Injection (VULN-001/002) Fixed**
  - Removed `shell=True` from `te/cli.py` and `llmc_mcp/server.py`

### 2025-12-11

- **Boxxie Agent Lives**
  - Tool tier gating removed
  - Aggressive Qwen prompting for tool usage

### 2025-12-10

- **Event-Driven RAG Service**
  - inotify-based file watching (~0% CPU when idle)
  - Instant response to file saves (<3s with debounce)

- **Distributed Enrichment Support**
  - Configure multiple Ollama servers in llmc.toml
  - T/s logging for inference speed visibility

### 2025-12-08

- **CLI UX Cleanup**
  - `llmc init` → `llmc repo init`
  - `llmc repo add` → `llmc repo register`
  - Removed completion clutter from help

### 2025-12-07

- **mcgrep - Semantic Grep for Code**
  - mgrep-style CLI with freshness-aware fallback
  - Commands: watch, status, init, stop

- **Repository Validation**
  - Validates llmc.toml, Ollama connectivity, model availability
  - BOM detection and auto-fix

- **Testing Demon Army**
  - Emilia orchestrator + 11 demon agents
  - GAP demon auto-generates SDDs

### 2025-12-05-06

- **MAASL (Multi-Agent Anti-Stomp Layer)**
  - 8-phase implementation
  - File locking, DB transaction guard, graph merge engine
  - 📄 Design: `planning/SDD_MAASL.md`

- **MCP Daemon Architecture**
  - HTTP/SSE transport, token auth, daemon manager
  - `rag_plan` observability tool

### 2025-12-03

- **FTS5 Stopwords Fix (P0 CRITICAL)**
  - "model" search returned 0 results
  - Fixed routing config and FTS5 tokenizer
  - Removed `@lru_cache` from config functions

### Earlier (Nov-Dec 2025)

- **Ruthless MCP Testing Agent (RMTA)** - Phase 1 complete
- **MCP Tool Alignment** - All handlers implemented
- **Automated Repository Onboarding** - 7 phases complete
- **Onboarding Configuration Validation** - Full validator
- **Path Traversal Security** - Already implemented, verified
- **Documentation Accuracy** - `llmc docs generate` exists
- **Enrichment Pipeline Tidy** - BackendAdapter, EnrichmentPipeline
- **Enrichment Path Weights** - Code-first prioritization
- **Surface Enriched Data** - rag_search_enriched, inspect, rag_stats
- **Deterministic Repo Docgen v2** - SHA256 idempotence, RAG freshness
- **System Friendliness** - os.nice(10), exponential backoff
- **MCP Daemon** - HTTP/SSE transport, auth middleware
- **MCP Tool Expansion** - where_used, lineage, inspect, stats, plan
- **Productization** - Unified llmc CLI with typer
- **Polyglot RAG (TypeScript)** - TreeSitterSchemaExtractor
- **CLI UX Progressive Disclosure** - Help on no args
- **Interactive Configuration Wizard** - `llmc repo register --interactive`
- **Clean Public Story** - Consolidated entrypoints
- **Modular Enrichment Plugins** - BackendAdapter, factory, registry
- **Symbol Importance Ranking** - Heuristic ranking for inspect
- **MCP Telemetry** - SQLite tool usage tracking
- **Remote LLM Provider Support** - Gemini, OpenAI, Anthropic, Groq
- **RUTA & Testing Demon Army** → Moved to `~/src/thunderdome/`

---

## How This File Works

When an item is completed in `ROADMAP.md`:
1. Move the summary here with completion date
2. Keep enough detail to remember what was done
3. Link to relevant docs/SDDs if they exist
