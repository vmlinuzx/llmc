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
