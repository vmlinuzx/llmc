# LLMC Roadmap

This roadmap focuses only on **active** work. Completed phases and big wins are moved to `ROADMAP_COMPLETED.md` so this file stays short and actionable.

Think of this as:

- **Now** – what the next focused work sessions should attack.
- **Next** – post-launch improvements that matter for day‑to‑day use.
- **Later** – deeper refactors, polish, and research.

---

## 1. Now (Release Focus – P0 / P1)

These are the things that make the current LLMC stack feel solid and intentional for you and for any future users.



### ~~1.2 Enrichment pipeline tidy-up~~ ✅ DONE

**Completed:** Dec 2025

**Goal:** Bring the enrichment pipeline closer to the design in the docs without over-engineering.

**📄 Design:** [`planning/SDD_Enrichment_Pipeline_Tidy.md`](planning/SDD_Enrichment_Pipeline_Tidy.md)

**Summary:**
- ✅ Phase 1: Extracted  `OllamaBackend` as proper `BackendAdapter` implementation (186 lines)
- ✅ Phase 2: Created `EnrichmentPipeline` class orchestrator (406 lines)
- ✅ Phase 3: Wired `service.py` to use pipeline directly (no more subprocess)

**Impact:** Clean architecture, direct function calls, foundation for remote providers (3.6)

### 1.2.1 Enrichment Path Weights & Code-First Prioritization

**Goal:** Prioritize enrichment of critical code paths over test code, docs, and vendor trash.

**📄 Design:** [`planning/SDD_Enrichment_Path_Weights.md`](planning/SDD_Enrichment_Path_Weights.md)

**Summary:**
- Configurable 1-10 weight scale for path patterns (lower = higher priority)
- "Highest weight wins" collision resolution for overlapping patterns
- Test code detection via path patterns AND content heuristics
- Priority formula: `final = base * (11 - weight) / 10`
- `--show-weights` debug mode for transparency

**Why:**
- Tests in `src/tests/` shouldn't block `src/core/router.py` enrichment
- Vendor code shouldn't compete with your actual code
- Different projects have different priorities (configurable via `llmc.toml`)

**Effort:** 3-4 hours | **Difficulty:** 🟡 Medium

---

### ~~1.3 Surface enriched data everywhere it matters~~ ✅ DONE

**Completed:** Nov-Dec 2025

- `rag_search_enriched` tool with graph enrichment modes
- `inspect` returns enrichment data and summaries
- `rag_stats` shows enrichment coverage
- Integration tests verify enrichment schema

### 1.4 Clean public story and remove dead surfaces

**Goal:** Reduce confusion and maintenance by cutting old interfaces.

- Tighten the README and top‑level docs:
  - Clearly state the supported entrypoints:
    - `llmc-rag`, `llmc-rag-nav`, `llmc-rag-repo`, `llmc-rag-daemon/service`, `llmc-tui`.
  - Call out what LLMC does *not* try to be (no hosted SaaS, no magic auto‑refactor).

### ~~1.6 System Friendliness (Idle Loop Throttling)~~ ✅ DONE

**Completed:** Dec 2025 - Implemented in `tools/rag/service.py`

- `os.nice(10)` at daemon startup
- Exponential backoff when idle (configurable base/max in `llmc.toml`)
- Interruptible sleep for signal handling
- Logging: "💤 Idle x{n} → sleeping..."

### ~~1.7 MCP Daemon with Network Transport~~ ✅ DONE

**Completed:** Dec 2025

- HTTP/SSE transport: `llmc_mcp/transport/http_server.py`
- API key auth middleware: `llmc_mcp/transport/auth.py`  
- Daemon manager with pidfiles/signals: `llmc_mcp/daemon.py`
- CLI integration in `llmc_mcp/cli.py`

### ~~1.8 MCP Tool Expansion~~ ✅ DONE

**Completed:** Dec 2025

- All tools implemented: `rag_where_used`, `rag_lineage`, `inspect`, `rag_stats`, `rag_plan`
- Stubs auto-generated from TOOLS list

---

## 2. Next (Post‑Launch P1)

These are things that make LLMC nicer to live with once the core system is “good enough”.

### ~~2.1 Productization and packaging~~ ✅ DONE

**Completed:** Dec 2025

- Unified `llmc` CLI with typer: init, index, search, enrich, graph, etc.
- Service management: `llmc service start/stop/status/logs`
- Repo management: `llmc service repo add/remove/list`
- Nav tools: `llmc nav search/where-used/lineage`
- TUI: `llmc tui` / `llmc monitor`

### ~~2.2 Polyglot RAG support~~ ✅ DONE

**Completed:** Dec 2025

**Goal:** Make the schema graph and RAG story work across more than just Python.

**📄 Design:** [`planning/SDD_Polyglot_RAG_TypeScript.md`](planning/SDD_Polyglot_RAG_TypeScript.md)  
**📄 Implementation:** [`planning/IMPL_Polyglot_RAG_TypeScript.md`](planning/IMPL_Polyglot_RAG_TypeScript.md)

**Summary:**
- ✅ `TreeSitterSchemaExtractor` base class for polyglot extraction
- ✅ `TypeScriptSchemaExtractor` for TypeScript/JavaScript (functions, classes, interfaces, types)
- ✅ Relation extraction: imports, calls, extends
- ✅ Integration with existing schema graph pipeline
- ✅ Multi-file TypeScript project support
- ✅ 6 unit tests + end-to-end integration test

**Results:**
- TypeScript/JavaScript files now indexed alongside Python
- Entities: functions, classes, interfaces, type aliases
- Relations: imports, function calls, class inheritance
- 14 entities extracted from 3-file test project

### 2.4 Deterministic Repo Docgen (v2)

**Goal:** Generate accurate, per-file repository documentation automatically with RAG-based freshness gating.

- Implement deterministic doc generation per file:
  - Single freshness gate: RAG must be current for exact file+hash.
  - SHA256 gating handled only by orchestrator.
  - Backend contract: JSON stdin → Markdown stdout (no chatter).
- Build graph context builder with deterministic ordering and caps.
- Create LLM backend harness with canonical prompt template.
- Output to `DOCS/REPODOCS/<relative_path>.md` structure.
- Add observability: counters, timers, and size metrics.
- Implement concurrency control with file locking.
- **Reference:** [SDD_Docgen_v2_for_Codex.md](file:///home/vmlinux/src/llmc/DOCS/planning/SDD_Docgen_v2_for_Codex.md)

---

## 3. Later (P2+ / R&D)

These are the “this would be awesome” items that are worth doing, but not at the cost of stability.

### 3.1 Modular enrichment plugins

**Goal:** Make it easy to add new backends (local or remote) without touching core code.

- Turn the enrichment backend definitions into a plugin‑style registry:
  - Configurable via `llmc.toml`.
  - Pluggable Python modules for custom backends.
- Document a “write your own backend” path for power users.

### 3.2 Symbol importance ranking for `rag inspect`

**Goal:** Reduce token bloat and make `inspect` more LLM‑friendly.

- Add a ranking scheme for symbols in a file:
  - Heuristics like "public API functions", "classes", and "callers with many edges" score higher.
- Update `rag inspect` / `inspect_entity` to:
  - Return a compact, ranked subset for LLMs by default.
  - Expose the full symbol list only on explicit request.

### 3.3 MCP Telemetry & Observability

**Goal:** Enable deep-dive analysis and monitoring while respecting user privacy.

- Implement privacy-aware telemetry system:
  - Configurable privacy tiers (none/metrics/metadata/arguments/full).
  - SQLite storage for queryable telemetry (`.llmc/mcp_telemetry.db`).
  - Automatic redaction of sensitive data (credentials, paths).
  - **Default: OFF** for public distribution (security-first).
- Add TUI dashboard integration:
  - Real-time metrics display (call counts, latencies, error rates).
  - Top tools and recent errors tracking.
  - Code execution trace viewer (privacy-gated).
- Implement retention policies with auto-cleanup.
- Add `get_telemetry` MCP tool for LLM self-analysis.

### 3.4 Multi-Agent Coordination & Anti-Stomp ✅ CODE COMPLETE

**Status:** Feature branch ready, pending integration testing

**Branch:** `feature/maasl-anti-stomp` (DO NOT MERGE YET)

MAASL (Multi-Agent Anti-Stomp Layer) - 8 phases implemented:
- Phase 1-3: Core lock manager, file protection, code protection
- Phase 4: DB transaction guard with SQLite coordination
- Phase 5: Graph merge engine for concurrent updates
- Phase 6: Docgen coordination  
- Phase 7: Introspection tools (MCP integration)
- Phase 8: Production hardening

**Before merge:**
- [ ] Multi-agent stress testing (3+ concurrent agents)
- [ ] Real-world usage validation
- [ ] Lint clean after concurrent edits

### 3.5 Comprehensive Repo Cleanup

**Goal:** Clean up build artifacts, cache files, and cruft throughout the entire repository.

**Prerequisites:**
- Documentation agent complete (for pre-cleanup docs sweep)

**Tasks:**
- Full documentation sweep of every file (via documentation agent)
- Identify and remove/move build artifacts:
  - `__pycache__/` directories
  - `.egg-info/` directories
  - Orphaned cache files
  - Temporary test outputs
  - Old backup files (`*~`, `*.bak`)
- Update `.gitignore` to prevent future artifact commits
- Create cleanup script for regular maintenance
- Document artifact management policy in `CONTRIBUTING.md`

**Priority:** Low (blocked on documentation agent completion)

**Estimated Effort:** 4-6 hours

### 3.6 Remote LLM Provider Support for Enrichment

**Goal:** Enable remote API providers (Gemini, OpenAI, Anthropic, Groq) in the enrichment cascade with production-grade reliability.

**📄 Design:** [`planning/SDD_Remote_LLM_Providers.md`](planning/SDD_Remote_LLM_Providers.md)

**Summary:**
- Add `RemoteBackend` adapter supporting multiple providers
- Implement reliability middleware: exponential backoff, rate limiting, circuit breaker
- Cost tracking with configurable daily/monthly caps
- Provider registry with auth, endpoints, and rate limits per provider

**Phases:** 8 phases, ~17-25 hours total
| Phase | Difficulty |
|-------|------------|
| RemoteBackend base class | 🟡 Medium |
| Gemini adapter | 🟢 Easy |
| Retry middleware (backoff) | 🟢 Easy |
| Rate limiter (token bucket) | 🟡 Medium |
| Circuit breaker | 🟢 Easy |
| Cost tracking + caps | 🟢 Easy |
| More providers (OpenAI, Anthropic, Groq) | 🟢 Easy |
| Testing | 🟡 Medium |

**Why Later:** Local Ollama works fine for now. This becomes important when you want to use cheaper/better remote models as fallback or for quality tiers.

---

## 4. How to use this roadmap

- When you start a work session, pull one item from **Now** and ignore the rest.
- When something from **Now** is truly finished, move its bullet (or a summarized version) into `ROADMAP_COMPLETED.md`.
- Periodically re‑shape **Next** and **Later** based on what is actually exciting or urgent.

The goal is not to track every tiny task, but to keep a **small, accurate map** of where LLMC is going *from here*.