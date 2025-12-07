# LLMC Roadmap

This roadmap focuses only on **active** work. Completed phases and big wins are moved to `ROADMAP_COMPLETED.md` so this file stays short and actionable.

Think of this as:

- **Now** – what the next focused work sessions should attack.
- **Next** – post-launch improvements that matter for day‑to‑day use.
- **Later** – deeper refactors, polish, and research.

---

## 1. Now (Release Focus – P0 / P1)

These are the things that make the current LLMC stack feel solid and intentional for you and for any future users.

### ~~1.0 Ruthless MCP Testing Agent (RMTA)~~ ✅ DONE (Phase 1)

**Completed:** Dec 2025

**Goal:** Systematically validate the MCP server through agent-based testing.

**📄 Design:** [`planning/HLD_Ruthless_MCP_Testing_Agent.md`](planning/HLD_Ruthless_MCP_Testing_Agent.md)  
**📄 AAR:** [`planning/AAR_MCP_Live_Testing_2025-12-04.md`](planning/AAR_MCP_Live_Testing_2025-12-04.md)

**Summary:**
- ✅ Phase 1: Shell harness + methodology complete
- ✅ MCP tool issues from 2025-12-04 AAR have been FIXED (see 1.0.1)
- ✅ Reports generated to `tests/REPORTS/`
- Extensive testing conducted with multiple ruth reports

**Remaining (P2):**
- [ ] Phase 2: Automated orchestrator (`llmc test-mcp --mode ruthless`)
- [ ] Phase 3: CI integration with quality gates
- [ ] Phase 4: Historical tracking and regression detection

---

### ~~1.0.1 MCP Tool Alignment and Implementation~~ ✅ DONE

**Completed:** Dec 2025

**Goal:** Fix all MCP tool discrepancies identified in 2025-12-04 AAR.

**📄 AAR:** [`planning/AAR_MCP_Live_Testing_2025-12-04.md`](planning/AAR_MCP_Live_Testing_2025-12-04.md)

**Summary:**
All "missing handler" issues from 2025-12-04 AAR have been resolved:

- ✅ `rag_where_used` - Implemented (server.py:1139-1157)
- ✅ `rag_lineage` - Implemented (server.py:1162-1181)
- ✅ `rag_stats` - Implemented (server.py:1218-1230)
- ✅ `inspect` - Implemented
- ✅ Bootstrap prompt path fixed

**Known Remaining Issues (P2):**
- `linux_proc_*` tools return stub/empty data (marked experimental)
- `linux_fs_edit` response metadata accuracy (cosmetic)

---

### ~~1.1 Automated Repository Onboarding~~ ✅ DONE

**Completed:** Dec 2025

**Goal:** Eliminate manual setup friction when adding new repositories.

**📄 Design:** [`planning/SDD_Repo_Configurator.md`](planning/SDD_Repo_Configurator.md)

**Summary:**
- ✅ All 7 phases complete
- ✅ `llmc repo add` generates complete `llmc.toml` with enrichment section
- ✅ Supports interactive and non-interactive modes
- ✅ Config template includes full `[enrichment]`, `[embeddings]`, and `[routing]` sections
- ✅ Validation available via `llmc repo validate` (see 1.1.1)

---

### ~~1.1.1 Onboarding Configuration Validation~~ ✅ DONE

**Completed:** Dec 2025

**Goal:** Catch config issues before they cause silent failures.

**Summary:**
Full validator implemented in `llmc/commands/repo_validator.py` (511 lines):

- ✅ Config schema validation (enrichment, embeddings, routing sections)
- ✅ Ollama connectivity checks with timeout handling
- ✅ Model availability verification
- ✅ BOM character detection and `--fix-bom` auto-fix
- ✅ `llmc repo validate` command integrated into CLI
- ✅ Default config template includes complete enrichment section

**CLI:**
```bash
llmc repo validate /path/to/repo           # Full validation
llmc repo validate /path/to/repo --fix-bom # Auto-fix BOM characters
llmc repo validate . --no-connectivity     # Skip network checks
```

**Remaining Polish (P2):**
- [ ] Auto-run validation after `repo add`
- [ ] Integration with `rag doctor`
- [ ] Embedding model availability check

---

### ~~1.2 Path Traversal Security Fix~~ ✅ FIXED

**Completed:** Dec 2025

**Goal:** Prevent `rag inspect` and related tools from reading files outside the repository boundary.

**Summary:**
Path traversal protection was **already implemented** in `tools/rag/inspector.py`:

- ✅ `PathSecurityError` exception class (line 58-60)
- ✅ Null byte injection blocked (line 72-73)
- ✅ Absolute paths outside repo rejected (lines 77-86)
- ✅ Relative traversal (`../`) blocked (lines 88-96)
- ✅ All paths resolved and validated against repo boundary

**Verification (2025-12-07):**
```bash
$ python3 -m tools.rag.cli inspect --path /etc/passwd
Error: Path '/etc/passwd' is outside repository boundary.

$ python3 -m tools.rag.cli inspect --path ../../../etc/passwd  
Error: Path '../../../etc/passwd' escapes repository boundary via traversal.
```

**Note:** Ren's 2025-12-04 report was accurate at the time, but this was fixed sometime between then and now. The implementation in `_normalize_path()` is thorough and handles edge cases correctly.

---

### 1.3 Documentation Accuracy Fix **P1**

**Status:** 🔴 Docs lie about capabilities

**Goal:** Remove or implement `llmc docs generate` - currently documented but doesn't exist.

**📄 Evidence:** Ren's Ruthless Report 2025-12-04

**Problem:**
26 documentation references to `llmc docs generate` command that doesn't exist:
- `DOCS/CLI_REFERENCE.md`
- `DOCS/Docgen_User_Guide.md`
- `DOCS/ROADMAP.md`
- `DOCS/planning/Docgen_v2_Final_Summary.md`

**Actual `llmc docs` commands:**
- `readme` - Display README
- `quickstart` - Display quickstart  
- `userguide` - Display user guide

**Options:**
1. **Implement the command** - Wire up existing docgen to CLI
2. **Remove documentation** - Delete all references
3. **Clarify** - Rename to `llmc debug autodoc generate` (which exists)

**Total Effort:** ~2-4 hours | **Difficulty:** 🟢 Easy (3/10)

**Why P1:**
- **User trust** - Documentation that lies erodes confidence
- **Onboarding friction** - New users try command and it fails

---

### ~~1.4 FTS5 Stopwords Filtering Critical Keywords~~ ✅ FIXED

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

### ~~1.5 Enrichment pipeline tidy-up~~ ✅ DONE

**Completed:** Dec 2025

**Goal:** Bring the enrichment pipeline closer to the design in the docs without over-engineering.

**📄 Design:** [`planning/SDD_Enrichment_Pipeline_Tidy.md`](planning/SDD_Enrichment_Pipeline_Tidy.md)

**Summary:**
- ✅ Phase 1: Extracted  `OllamaBackend` as proper `BackendAdapter` implementation (186 lines)
- ✅ Phase 2: Created `EnrichmentPipeline` class orchestrator (406 lines)
- ✅ Phase 3: Wired `service.py` to use pipeline directly (no more subprocess)

**Impact:** Clean architecture, direct function calls, foundation for remote providers (3.6)

### ~~1.5.1 Enrichment Path Weights & Code-First Prioritization~~ ✅ DONE

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

### ~~1.6 Surface enriched data everywhere it matters~~ ✅ DONE

**Completed:** Nov-Dec 2025

- `rag_search_enriched` tool with graph enrichment modes
- `inspect` returns enrichment data and summaries
- `rag_stats` shows enrichment coverage
- Integration tests verify enrichment schema

### ~~1.7 Deterministic Repo Docgen (v2)~~ ✅ DONE
**Completed:** Dec 2025

**Goal:** Generate accurate, per-file repository documentation automatically with RAG-based freshness gating.

**📄 Design:** [`planning/SDD_Docgen_v2_for_Codex.md`](planning/SDD_Docgen_v2_for_Codex.md)
**📄 Completion Report:** [`planning/Docgen_v2_Final_Summary.md`](planning/Docgen_v2_Final_Summary.md)

**Summary:**
- ✅ Implemented SHA256-based idempotence
- ✅ RAG-aware freshness gating
- ✅ Graph context integration
- ✅ Shell backend with JSON protocol
- ✅ Concurrency control with file locks
- ✅ CLI: `llmc debug autodoc generate` and `llmc debug autodoc status`
- ✅ 100% test pass rate (33 tests)

### ~~1.8 System Friendliness (Idle Loop Throttling)~~ ✅ DONE

**Completed:** Dec 2025 - Implemented in `tools/rag/service.py`

- `os.nice(10)` at daemon startup
- Exponential backoff when idle (configurable base/max in `llmc.toml`)
- Interruptible sleep for signal handling
- Logging: "💤 Idle x{n} → sleeping..."

### ~~1.9 MCP Daemon with Network Transport~~ ✅ DONE

**Completed:** Dec 2025

- HTTP/SSE transport: `llmc_mcp/transport/http_server.py`
- API key auth middleware: `llmc_mcp/transport/auth.py`  
- Daemon manager with pidfiles/signals: `llmc_mcp/daemon.py`
- CLI integration in `llmc_mcp/cli.py`

### ~~1.10 MCP Tool Expansion~~ ✅ DONE

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

### ~~2.3 CLI UX - Progressive Disclosure~~ ✅ DONE
**Completed:** Dec 2025

**Goal:** Ensure all CLI commands provide helpful guidance on errors instead of cryptic messages like "Missing command."

**Summary:**
- ✅ `llmc-rag-service` (daemon) shows help on no args
- ✅ `llmc-rag-nav` shows help on no args
- ✅ `llmc-tui` shows help on --help
- ✅ Added examples to all top-level help screens
- ✅ Consistent "tree-style" help overview for all tools


---

## 3. Later (P2+ / R&D)

These are the “this would be awesome” items that are worth doing, but not at the cost of stability.

### ~~3.1 Clean public story and remove dead surfaces~~ ✅ DONE

**Completed:** Dec 2025

**Goal:** Reduce confusion and maintenance by cutting old interfaces.

**Summary:** Consolidated entrypoints around `llmc` and `llmc-mcp`. Removed legacy scripts from `pyproject.toml`. Updated README.


### ~~3.2 Modular enrichment plugins~~ ✅ DONE
**Completed:** Dec 2025
**Goal:** Make it easy to add new backends (local or remote) without touching core code.
**Summary:** Implemented `BackendAdapter`, `enrichment_factory`, and plugin registry.


### ~~3.2 Symbol importance ranking for `rag inspect`~~ ✅ DONE
**Completed:** Dec 2025
**Goal:** Reduce token bloat and make `inspect` more LLM‑friendly.
**Summary:** Implemented heuristic ranking (Kind, Name, Size, Connectivity) to prioritize important symbols.


### ~~3.3 MCP Telemetry & Observability~~ ✅ DONE
**Completed:** Dec 2025
**Goal:** Gain visibility into how agents use the tools.
**Summary:** Implemented SQLite-backed tool usage tracking and exposed via `llmc stats`.


### ~~3.4 Multi-Agent Coordination & Anti-Stomp~~ ✅ DONE

**Completed:** Dec 2025

**Goal:** Prevent agents from stomping on each other's work (files, DB, graph) during concurrent execution.

**Validation:** [`planning/MAASL_VALIDATION_CHECKLIST.md`](planning/MAASL_VALIDATION_CHECKLIST.md)



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


### ~~3.5 Repo Cleanup & Dead Code Removal~~ ✅ DONE
**Completed:** Dec 2025
**Goal:** Remove unused code, consolidate duplicate logic, and reduce technical debt.
**Summary:** Removed legacy scripts, consolidated core utilities, and cleaned up CLI entry points.


### ~~3.6 Remote LLM Provider Support for Enrichment~~ ✅ DONE
**Completed:** Dec 2025
**Goal:** Enable remote API providers (Gemini, OpenAI, Anthropic, Groq) in the enrichment cascade with production-grade reliability.
**Summary:** Implemented `RemoteBackend`, adapters for major providers, circuit breakers, rate limiting, and cost tracking.


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

| Phase | Description | Difficulty | Effort | Status |
|-------|-------------|------------|--------|--------|
| 0 | Trace recorder + artifact plumbing | 🟢 Easy (3/10) | 4-8h | ✅ Done |
| 1 | Scenario schema + manual runner | 🟡 Medium (4/10) | 6-10h | ✅ Done |
| 2 | User Executor Agent | 🟡 Medium (6/10) | 12-16h | ✅ Done |
| 3 | Judge Agent + basic properties | 🟡 Medium (7/10) | 14-20h | ✅ Done |
| 4 | Metamorphic testing (PMRE) | 🟡 Medium (7/10) | 14-20h | ✅ Done |
| 5 | CI integration + gates | 🟡 Medium (5/10) | 8-12h | |
| 6 | Advanced scenario generation | 🔴 Hard (8/10) | 20-30h | |

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