# LLMC Roadmap – Completed Work

This file tracks the **big, meaningful things that are already done** so the main `ROADMAP.md` can stay focused on what is next.

It is not an exhaustive changelog; it is a brag sheet and a memory aid.

---

## 1. Major Phases Completed

### 1.1 Phase 1 – DB / FTS foundation

- Built the core SQLite‑backed RAG index (`.rag/index_v2.db`):
  - Span table with file/line metadata.
  - Full‑text search tables for cheap local queries.
- Implemented CLI commands to:
  - Index a repo from scratch.
  - Sync incrementally from git diff or stdin path lists.
- Added tests to keep the basic DB and FTS plumbing honest.

### 1.2 Phase 2 – Graph enrichment & builder orchestration

- Implemented enrichment DB helpers and `EnrichmentRecord` types.
- Wired joins between spans and enrichments.
- Folded enrichment fields into `Entity.metadata` during graph build.
- Added tests around graph/enrichment merge behavior.

### 1.3 Phase 3 – RAG Nav tools and Context Gateway

- Implemented `llmc-rag-nav` tools:
  - `search`, `where-used`, `lineage` over the `.llmc` graph and manifest.
- Built the freshness envelope and context gateway:
  - Per‑repo index status and slice freshness tracking.
  - Gateway that prefers **fresh** RAG data and falls back to live repo tools when stale.
- Wrote tests for index status, freshness logic, and the gateway behavior.

---

## 2. Enrichment, Daemon, and Repo Management

### 2.1 Enrichment data integration (DB → Graph → API)

- Connected enrichment data end‑to‑end:
  - From `enrichments` table in the DB.
  - Into the schema graph.
  - Out through `tools.rag_nav` JSON envelopes.
- Added tests to ensure enrichment fields show up in tool results and handle failures gracefully.

### 2.2 Enrichment backends abstraction

- Created `tools/rag/enrichment_backends.py`:
  - Backend and backend‑chain abstractions.
  - Attempt records with timing and success/failure flags.
- Integrated backend logic with existing enrichment flows.

### 2.3 RAG daemon and service correctness

- Fixed the daemon to use the real enrichment pipeline instead of fake summaries.
- Verified that:
  - Enriched spans are written correctly.
  - Routing behavior and logging/metrics behave as expected.
- Wrapped the daemon in `llmc-rag-service` with friendly `start|stop|status` behavior.

### 2.4 Repo registry and workspace safety

- Implemented a repo registry and workspace planner:
  - `.llmc` workspaces under safe locations only.
  - Path validation to avoid traversal and unsafe roots.
- Added `doctor-paths`, `snapshot`, and `clean` entrypoints for:
  - Diagnosing path policy.
  - Capturing workspace snapshots.
  - Cleaning local RAG state safely.

### 2.5 Enrichment hardening and operator docs

- Documented `DOCS/RAG_Enrichment_Hardening.md` covering config, `enforce_latin1_enrichment` behavior, retries, timeouts, and backend fallbacks.
- Added a structured triage checklist for common enrichment issues (stuck jobs, backend flapping, DB pollution).

### 2.6 Database Maintenance (Auto-Vacuum)

- Implemented automatic SQLite `VACUUM` maintenance in the enrichment loop.
- Configurable via `llmc.toml` (`[enrichment] vacuum_interval_hours`, default 24).
- Tracks execution time per repo to ensure minimal performance impact.

### 2.7 MCP Bootstrap Prompt Refactor

- Moved the large `BOOTSTRAP` constant from `llmc_mcp/server.py` to `llmc_mcp/prompts.py`.
- Updated `llmc_mcp/server.py` to import and use the prompt from the new module.
- Ensured no changes to the prompt's content.

### 2.8 MCP Tool Expansion (Phase 1)

- Added P0 navigation tools to MCP: `rag_where_used`, `rag_lineage`, `inspect`.
- Added P1 observability tool: `rag_stats`.
- All tools support both classic MCP mode and Code Execution mode (via stubs).

### 2.9 Normalized RAG Scores

- Implemented normalized scoring (0-100) alongside raw ranking scores.
- Updated `SpanSearchResult` data model and search logic.
- Updated CLI and TUI to display normalized scores for better human readability.
- Documented scoring logic in User Guide.

---

## 3. Desktop Commander / Tools Surface

### 3.1 Tool manifest for Desktop Commander

- Wrote `DOCS/TOOLS_DESKTOP_COMMANDER.md` as the authoritative manifest for:
  - `llmc-rag-nav` tools.
  - Supporting context and safety notes.
- Ensured the manifest:
  - Matches the actual CLI/tool behavior.
  - Is discoverable by agents and by humans.

### 3.2 Nav tools and enriched tool contracts

- Standardized JSON envelopes for:
  - Search.
  - Where‑used.
  - Lineage.
- Updated tests (`test_rag_nav_tools`, `test_rag_nav_enriched_tools`, etc.) to lock these contracts in.

---

## 4. RAG Freshness & Safety

### 4.1 Freshness envelope and safe fallback

- Implemented `tools.rag.freshness` module and index status tracking.
- Ensured all RAG‑consuming tools can:
  - Check freshness before trusting the index.
  - Fall back to filesystem/AST tools when RAG is stale or broken.
- Added tests for:
  - Fresh vs stale vs unknown states.
  - Gateway behavior under error conditions.

### 4.2 Ruthless testing infrastructure

- Added focused tests for:
  - Daemon behavior under failure.
  - Freshness gateway.
  - Nav tools and index status.
- Created scripts like `llmc_test_rag_freshness.sh` and other helpers to:
  - Run targeted test suites.
  - Give quick signal on the most critical paths.

---

## 5. RAG Nav search quality and graph indices

Carried from prior roadmap “Recently Completed (Highlights)”:

- Added configurable reranker weights:
  - Via `.llmc/rag_nav.ini` and `RAG_RERANK_W_*` env vars.
  - With safe normalization defaults.
- Introduced canary/search evaluation harnesses:
  - `tools.rag.eval.search_eval` and sample canary queries.
- Implemented graph‑indexed where‑used and lineage:
  - Over `.llmc/rag_graph.json`.
  - Wired through the Context Gateway with graceful fallbacks.

---

### 6. Template, TUI, and UX Wins

- Piped RAG planner output into wrappers so Codex/Claude/Gemini can consume indexed spans automatically.
- Locked an MVP stack and scope for the template‑builder UX.
- Built and wired the LLMC TUI:
  - Monitor, search, inspector, and config screens.
  - Basic keyboard navigation and layout.
- Implemented comprehensive TE Analytics TUI enhancements:
  - Top bar with time range selector and enriched vs. pass-through ratio gauge.
  - Enhanced Unenriched Candidates panel with sorting, new columns (total size, avg latency, est. tokens).
  - Enhanced Enriched Actions panel with savings metrics, latency impact, and status indicators.
  - Recent Activity Stream with real-time command activity.
  - Persistent bottom status bar with key metrics.
  - Optional command category breakdown.

---

## 7. How to use this file

- When you finish a meaningful roadmap item from `ROADMAP.md`, move a short summary into one of the sections above (or add a new section).
- Keep the wording high‑level and human; the detailed implementation lives in code, tests, and SDDs.
- Use this as your **“look what I already built”** reminder when the system feels overwhelming.

---

## 8. Modular Architecture & Ruthless Routing

### 8.1 Modular Embeddings (v0.5.5)

- Refactored embedding system to support configurable profiles (local/remote) and provider abstraction.
- Enabled granular control over models, dimensions, and provider-specific settings via `llmc.toml`.
- Added automatic schema migration for profile-aware storage.

### 8.2 Ruthless Query Routing (v0.5.6)

- Overhauled query classification with robust regexes and signal-based scoring.
- Implemented "Ruthless" testing suite covering extreme edge cases (500k+ chars, unicode, injection).
- Added configurable conflict resolution policy (Code vs ERP) and tool context overrides.
- Fixed critical crashes and fenced code detection bugs.
- Added comprehensive routing metrics and debugging info (`target_index`).

### 8.3 Reliability & Observability

- **RAG Doctor:** Implemented health monitoring and diagnostics for the RAG pipeline.
- **Telemetry Hardening:** Switched TE telemetry to SQLite for reliability and consistency.
- **Code Quality:** Massive linting cleanup and test suite repairs.

### 8.4 Polyglot RAG Support (Dec 2025)

- Extended schema extraction beyond Python to support TypeScript and JavaScript.
- **TreeSitterSchemaExtractor** base class for language-agnostic entity/relation extraction.
- **TypeScriptSchemaExtractor** with full support for:
  - Functions (regular, arrow, methods)
  - Classes with inheritance tracking
  - Interfaces and type aliases
  - Import/export statements with symbol resolution
- Relation extraction: imports, function calls, class inheritance.
- Integration: Multi-file TS/JS projects indexed alongside Python.
- Test coverage: 6 unit tests + end-to-end integration test.
- **Impact:** LLMC now works with TypeScript/JavaScript codebases, enabling polyglot repos.

### 8.5 Multi-Agent Coordination & Anti-Stomp (Dec 2025)

- **Goal:** Prevent agents from stomping on each other's work (files, DB, graph) during concurrent execution.
- **Summary:**
  - ✅ Implemented `LockManager` with lease-based mutexes and fencing tokens
  - ✅ Created `MAASL` facade for `call_with_stomp_guard`
  - ✅ Protected critical resources: `CRIT_CODE` (files), `CRIT_DB` (sqlite), `MERGE_META` (graph), `IDEMP_DOCS` (docgen)
  - ✅ Validated with multi-agent stress tests (3-5 concurrent agents)
  - ✅ Verified zero data loss and clean linting under load
- **Validation:** [`planning/MAASL_VALIDATION_CHECKLIST.md`](planning/MAASL_VALIDATION_CHECKLIST.md)

### 3.1 Clean Public Story & Dead Surface Removal (Dec 2025)

- **Goal:** Reduce confusion by consolidating around the unified `llmc` CLI.
- **Summary:**
  - ✅ Updated `pyproject.toml` to remove legacy entrypoints (`llmc-rag`, `llmc-yolo`, `llmc-doctor`, `llmc-profile`).
  - ✅ Updated `README.md` to focus exclusively on `llmc` and `llmc service`.
  - ✅ Removed "Development Mode" instructions that encouraged using raw wrapper scripts.
  - ✅ Clarified capabilities section to refer to `llmc service` instead of legacy script names.

### 3.2 Modular Enrichment Plugins (Dec 2025)

- **Goal:** Make it easy to add new backends (local or remote) without touching core code.
- **Summary:**
  - ✅ Implemented `BackendAdapter` protocol and `BackendCascade`.
  - ✅ Created `enrichment_factory.py` for dynamic backend instantiation.
  - ✅ Refactored `OllamaBackend` to use the new adapter interface.
  - ✅ Added support for `llmc.toml` based backend configuration.

### 3.6 Remote LLM Provider Support (Dec 2025)

- **Goal:** Enable remote API providers (Gemini, OpenAI, Anthropic, Groq) in the enrichment pipeline.
- **Summary:**
  - ✅ Implemented `RemoteBackend` base class.
  - ✅ Added adapters for Gemini, OpenAI (and compatible), Anthropic.
  - ✅ Implemented reliability middleware: `CircuitBreaker`, `RateLimiter`, `CostTracker`.
  - ✅ Added tiered failover configuration in `llmc.toml`.
  - ✅ Documented usage in `DOCS/Remote_LLM_Providers_Usage.md`.

### 3.2 Symbol Importance Ranking (Dec 2025)

- **Goal:** Reduce token bloat by prioritizing important symbols in `inspect`.
- **Summary:**
  - ✅ Implemented `_calculate_entity_score` heuristic (Kind, Name, Size, Connectivity).
  - ✅ Updated `inspect_entity` to sort defined symbols by importance score.
  - ✅ Verified ranking: Classes > Functions > Variables; Public > Private.

### 3.3 MCP Telemetry & Observability (Dec 2025)

- **Goal:** Gain visibility into how agents use the tools.
- **Summary:**
  - ✅ Implemented `SQLiteMetricsCollector` in `llmc_mcp`.
  - ✅ Added `sqlite_enabled` and `sqlite_path` to `McpObservabilityConfig`.
  - ✅ Integrated metrics collection into `ObservabilityContext`.
  - ✅ Updated `llmc stats` to display tool usage stats from `telemetry.db`.

### 3.5 Repo Cleanup & Dead Code Removal (Dec 2025)

- **Goal:** Remove unused code, consolidate duplicate logic, and reduce technical debt.
- **Summary:**
  - ✅ Removed legacy scripts (`llmc-rag`, `llmc-rag-daemon`, etc.) in favor of unified CLI.
  - ✅ Consolidated `find_repo_root` and `load_config` into `llmc.core`.
  - ✅ Refactored `tools.rag.config` and `tools.rag.utils` to use core utilities.
  - ✅ Removed deprecated CLI entry points from `pyproject.toml`.







## 9. CLI Polish & Consistency

### 9.1 Documentation Accuracy (Dec 2025)

- Implemented `llmc docs generate` (previously hidden as `debug autodoc`).
- Fixed DB path discovery and argument handling.
- Resolved discrepancy between documentation and implementation.
