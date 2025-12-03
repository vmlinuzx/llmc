# LLMC Roadmap

This roadmap focuses only on **active** work. Completed phases and big wins are moved to `ROADMAP_COMPLETED.md` so this file stays short and actionable.

Think of this as:

- **Now** – what the next focused work sessions should attack.
- **Next** – post-launch improvements that matter for day‑to‑day use.
- **Later** – deeper refactors, polish, and research.

---

## 1. Now (Release Focus – P0 / P1)

These are the things that make the current LLMC stack feel solid and intentional for you and for any future users.

### 1.1 Automated Repository Onboarding **P0**

**Status:** Active Development (Dec 2025)

**Goal:** Eliminate manual setup friction when adding new repositories. One command should handle everything: workspace creation, config generation, initial indexing, and MCP readiness.

**📄 Design:** [`planning/SDD_Repo_Onboarding_Automation.md`](planning/SDD_Repo_Onboarding_Automation.md)

**Problem:**
- Current `llmc-rag-repo add` only creates workspace structure
- Users must manually copy `llmc.toml`, update `allowed_roots`, run indexing, configure enrichment
- 6+ manual steps → high friction, inconsistent configs, poor UX
- **Architecture issue:** Business logic in CLI instead of service layer

**Solution:**
- Implement `RAGService.onboard_repo()` as **service-layer orchestrator**
- CLI becomes thin wrapper delegating to service
- Automated phases:
  1. Workspace creation (✅ existing)
  2. `llmc.toml` generation with path substitution 🆕
  3. Initial indexing (leverage `process_repo()`) 🆕
  4. Interactive enrichment prompt 🆕
  5. MCP readiness instructions 🆕
  6. Daemon integration 🆕

**Implementation Phases:**
- [ ] Phase 1: Core `onboard_repo()` method (4-5h)
- [ ] Phase 2: Config template generation (3-4h)
- [ ] Phase 3: Initial indexing integration (2-3h)
- [ ] Phase 4: Optional enrichment (2-3h)
- [ ] Phase 5: MCP instructions \u0026 polish (2h)
- [ ] Phase 6: CLI wrapper integration (2h)
- [ ] Phase 7: Testing \u0026 docs (3-4h)

**Total Effort:** 18-24 hours | **Difficulty:** 🟡 Medium

**Success Criteria:**
- ✅ One command: `llmc-rag-repo add /path/to/repo` → fully ready
- ✅ MCP queries work immediately after onboarding
- ✅ Non-interactive mode (`--yes`) for CI/automation
- ✅ Clear progress indicators and error messages
- ✅ End-to-end tests with real repos

**Why P0:** **Productization blocker.** This is the #1 UX friction point preventing smooth multi-repo workflows and adoption by other developers.

---

### ~~1.1.5 FTS5 Stopwords Filtering Critical Keywords~~ ✅ FIXED

**Completed:** Dec 2025-12-03

**Severity:** P0 CRITICAL - RAG search completely broken for core ML/AI queries

**Problem:**
- Single keyword "model" returned **0 results** (expected: thousands)
- ANY multi-word query containing "model" returned 0 results
- Identical queries with "model" removed returned 6000+ results
- **Root Cause:** SQLite FTS5 default `porter` tokenizer includes English stopwords list
- Default stopwords include: "model", "system", "data", etc. - **fundamental ML/AI terms**
- LLMC is an ML/AI codebase - these terms are CRITICAL, not noise!

**Impact Assessment:**
- Makes RAG essentially unusable for core functionality searches
- Affected queries: "embedding model", "LLM model", "model routing", "model selection"
- Affects: `embeddings.profiles`, model selection, routing configuration
- **Broke searches for the literal thing the system is designed to work with**

**Fix (2025-12-03):**
- ✅ **PRIMARY BUG:** Fixed routing config - `erp` route pointed to non-existent `emb_erp` table
  - Changed `[embeddings.routes.erp]` index from `emb_erp` → `embeddings` in `llmc.toml`
  - This was the actual cause of "model" returning 0 results (query routed to missing table)
- ✅ **SECONDARY BUG (FTS):** Changed FTS5 tokenizer from `porter` to `unicode61` (no stopwords)
  - Updated `tools/rag/database.py::_ensure_fts()` table creation
  - Fixes FTS-based search (used by navigation tools)
- ✅ **CACHING BUG:** Removed `@lru_cache` from config functions (config.py)
  - Removed caching from `load_config()`, `resolve_route()`, `get_route_for_slice_type()`
  - Config changes now immediately visible without daemon restart
  - Performance impact: 0.9ms per request = 0.2% overhead (negligible)
- ✅ Created migration script: `scripts/migrate_fts5_no_stopwords.py`
- ✅ Migrated LLMC database: 5,776 enrichments reindexed
- ✅ Regression tests: `tests/test_fts5_stopwords_regression.py`
- ✅ Verified fix: "model" now returns 5 results with 0.915-1.000 scores (was 0)

**Files Modified:**
- `llmc.toml` - Fixed erp route: `index = "embeddings"` (was `emb_erp`)
- `tools/rag/config.py` - Removed `@lru_cache` from config functions
- `tools/rag/database.py` - FTS5 table creation with unicode61 tokenizer
- `scripts/migrate_fts5_no_stopwords.py` - Migration script for existing DBs
- `tests/test_fts5_stopwords_regression.py` - Regression tests for critical keywords

**Testing:**
```bash
# Verify migration worked
python3 scripts/migrate_fts5_no_stopwords.py /path/to/repo

# Run regression tests
pytest tests/test_fts5_stopwords_regression.py -v

# Manual validation
llmc-cli rag search "model"  # Should return results, not 0
```

**Prevention:**
- Added regression tests for critical ML/AI domain keywords
- Documented in code comments why unicode61 is required for technical search
- Test verifies FTS table uses unicode61 tokenizer

**Lessons Learned:**
- Never use generic NLP preprocessing defaults for domain-specific technical search
- SQLite FTS5 defaults are optimized for English prose, not code/technical docs
- Critical domain vocabulary must be tested in regression suite
- Search zero-result rate should be monitored in CI/CD
- **`@lru_cache` on config loading is an anti-pattern for long-running daemons**
  - Config edits weren't picked up without manual `.cache_clear()` calls AND daemon restart
  - The "fix config, reload" workflow was completely broken
  - Simple is better: reload on every request (0.2% overhead is negligible)

---

### ~~1.2 Enrichment pipeline tidy-up~~ ✅ DONE

**Completed:** Dec 2025

**Goal:** Bring the enrichment pipeline closer to the design in the docs without over-engineering.

**📄 Design:** [`planning/SDD_Enrichment_Pipeline_Tidy.md`](planning/SDD_Enrichment_Pipeline_Tidy.md)

**Summary:**
- ✅ Phase 1: Extracted  `OllamaBackend` as proper `BackendAdapter` implementation (186 lines)
- ✅ Phase 2: Created `EnrichmentPipeline` class orchestrator (406 lines)
- ✅ Phase 3: Wired `service.py` to use pipeline directly (no more subprocess)

**Impact:** Clean architecture, direct function calls, foundation for remote providers (3.6)

### ~~1.2.1 Enrichment Path Weights & Code-First Prioritization~~ ✅ DONE

**Completed:** Dec 2025

**✅ BUG FIX (2025-12-03):** Fixed database query ordering bug that was causing sequential processing of markdown files instead of prioritizing code files. Changed `ORDER BY spans.id` to `ORDER BY RANDOM()` for diverse sampling. See `DOCS/planning/FIX_SUMMARY_Code_First_Prioritization.md` for details.

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

### 1.4 Deterministic Repo Docgen (v2)

**Goal:** Generate accurate, per-file repository documentation automatically with RAG-based freshness gating.

**Why Now:** Need this to properly document the system before doing any public-facing cleanup. The docgen will help create the clean story.

**📄 Design:** [`planning/SDD_Docgen_v2_for_Codex.md`](planning/SDD_Docgen_v2_for_Codex.md)

**Tasks:**
- Implement deterministic doc generation per file:
  - Single freshness gate: RAG must be current for exact file+hash.
  - SHA256 gating handled only by orchestrator.
  - Backend contract: JSON stdin → Markdown stdout (no chatter).
- Build graph context builder with deterministic ordering and caps.
- Create LLM backend harness with canonical prompt template.
- Output to `DOCS/REPODOCS/<relative_path>.md` structure.
- Add observability: counters, timers, and size metrics.
- Implement concurrency control with file locking.

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

### 2.3 CLI UX - Progressive Disclosure (Partial ✅)

**Status:** Started Dec 2025

**Goal:** Ensure all CLI commands provide helpful guidance on errors instead of cryptic messages like "Missing command."

**📝 Progress:**
- ✅ **Phase 1 (Dec 2025):** Fixed main CLI subcommands
  - `llmc-cli service` now shows available commands instead of error
  - `llmc-cli nav`, `llmc-cli docs`, `llmc-cli service repo` all show help
  - Implementation: Added `no_args_is_help=True` to all Typer subapps

**🔲 Remaining Work:**
- [ ] Audit all CLI scripts in `scripts/` for consistent help patterns
- [ ] Add progressive disclosure to `llmc-rag-service`
- [ ] Create CLI UX guidelines document
- [ ] Ensure consistent error messages across all commands
- [ ] Add example usage to every command help text

**Why:**
- Users shouldn't have to guess what commands exist
- Error messages should guide users to success
- Follows modern CLI best practices (e.g., `git`, `kubectl`)

**Effort:** 4-6 hours total | **Difficulty:** 🟢 Easy


---

## 3. Later (P2+ / R&D)

These are the “this would be awesome” items that are worth doing, but not at the cost of stability.

### 3.1 Clean public story and remove dead surfaces

**Goal:** Reduce confusion and maintenance by cutting old interfaces.

**Why Later:** Premature to do this before the system is fully documented and stable. Repo docgen (1.4) will help create the clean story first.

**Tasks:**
- Tighten the README and top-level docs:
  - Clearly state the supported entrypoints:
    - `llmc-rag`, `llmc-rag-nav`, `llmc-rag-repo`, `llmc-rag-daemon/service`, `llmc-tui`.
  - Call out what LLMC does *not* try to be (no hosted SaaS, no magic auto-refactor).

### 3.2 Modular enrichment plugins

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


### 3.5 RAG Scoring & Ranking Research (R&D)

**Goal:** Systematically tune RAG scoring weights to surface code over docs for implementation queries.

**Problem (2025-12-03):**
- Semantic search for "mcp bootstrap tools server" returns 20 markdown files before any `.py`
- Docs are verbose and keyword-rich → dominate BM25 and embedding similarity
- Users searching for implementation want code, not documentation about code

**Current Stopgap (search.py, rerank.py):**
- Added `_extension_boost()` to boost `.py` (+0.08) and penalize `.md` (-0.06)
- Updated `rerank.py` weights: bm25=55%, uni=18%, bi=12%, path=7%, lit=2%, ext=6%
- **This is a hack.** Needs proper research.

**Research Questions:**
1. What's the optimal weight distribution for code-focused queries vs doc-focused queries?
2. Should we route queries differently based on intent detection?
3. How do enrichment summaries affect semantic similarity? (docs have verbose summaries)
4. Should we embed code and docs in separate vector spaces?
5. What metrics define "good" search results? (MRR, NDCG, user satisfaction proxy?)

**Proposed Approach:**
- Build a test corpus of queries with known "correct" answers
- Implement A/B scoring framework to compare weight configurations
- Add query intent classification (code vs docs vs mixed)
- Consider separate indices for code vs documentation
- Evaluate cross-encoder reranking (expensive but accurate)

**Why R&D:** This is a proper machine learning / information retrieval research problem. The current hack works for obvious cases but will fail on nuanced queries. Need systematic experimentation.

**Effort:** 20-40 hours research + implementation | **Difficulty:** 🔴 Hard (research)


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

### 3.7 RUTA - Ruthless User Testing Agent (P3)

**Goal:** Automated end-to-end user flow testing through multi-agent simulation, property-based testing, and metamorphic relations.

**📄 Design:** [`planning/SDD_RUTA_Ruthless_User_Testing_Agent.md`](planning/SDD_RUTA_Ruthless_User_Testing_Agent.md)

**Problem:**
- Manual testing catches obvious bugs, but subtle issues slip through (example: "model" search bug)
- Need automated detection of:
  - Tool usage correctness and capability mismatches
  - Semantically weird failures (queries that should work but silently fail)
  - Environment lies (claiming tools are available when they're broken/blocked)
  - User flow regressions across releases

**Solution:**
RUTA uses simulated end users to exercise LLMC through **real public interfaces** (CLI, MCP, TUI, HTTP) and then judges the results:

1. **User Executor Agent** - simulated user completing realistic tasks
2. **Trace Recorder** - captures all tool calls, prompts, responses, metrics
3. **Judge Agent** - evaluates runs against properties and metamorphic relations
4. **Property/Metamorphic Relation Engine (PMRE)** - defines expectations like:
   - "Adding word 'model' to search must not reduce results to zero"
   - "Word order swap should give similar results (Jaccard >= 0.5)"
   - "Tool X must be used for scenario Y"
5. **Incident Reports** - structured P0-P3 findings with evidence from traces

**Architecture:**
- Scenario definitions in YAML (`tests/usertests/*.yaml`)
- JSONL trace logs with tool calls, latencies, errors
- JSON + Markdown reports for CI and human review
- CLI: `llmc usertest run --suite <name>`

**Phased Implementation:**

| Phase | Description | Difficulty | Effort |
|-------|-------------|------------|--------|
| 0 | Trace recorder + artifact plumbing | 🟢 Easy (3/10) | 4-8h |
| 1 | Scenario schema + manual runner | 🟡 Medium (4/10) | 6-10h |
| 2 | User Executor Agent | 🟡 Medium (6/10) | 12-16h |
| 3 | Judge Agent + basic properties | 🟡 Medium (7/10) | 14-20h |
| 4 | Metamorphic testing (PMRE) | 🟡 Medium (7/10) | 14-20h |
| 5 | CI integration + gates | 🟡 Medium (5/10) | 8-12h |
| 6 | Advanced scenario generation | 🔴 Hard (8/10) | 20-30h |

**Total Effort:** 78-116 hours (10-14 days)

**Success Criteria:**
- ✅ Automated detection of "model search" class bugs before production
- ✅ CI fails on P0 incidents (configurable thresholds)
- ✅ Rich incident reports with trace evidence
- ✅ Metamorphic relations for search, enrichment, tool usage
- ✅ No internal API dependencies (tests use same paths as users)

**Why P3:** 
- Powerful for regression prevention and quality gates
- Requires significant upfront investment in agent infrastructure
- Current manual testing + existing test suite provides baseline coverage
- Best value when system stabilizes and user flows are well-established

**Complements:**
- **Ruthless Security Agent** - security posture and sandbox boundaries
- **Ruthless System Testing Agent** - core functional tests and internal APIs
- **RUTA** - end-to-end user flows and semantic correctness

---

## 4. How to use this roadmap

- When you start a work session, pull one item from **Now** and ignore the rest.
- When something from **Now** is truly finished, move its bullet (or a summarized version) into `ROADMAP_COMPLETED.md`.
- Periodically re‑shape **Next** and **Later** based on what is actually exciting or urgent.

The goal is not to track every tiny task, but to keep a **small, accurate map** of where LLMC is going *from here*.