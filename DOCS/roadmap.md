# LLMC Roadmap

This roadmap focuses only on **active** work. Completed phases and big wins are moved to `ROADMAP_COMPLETED.md` so this file stays short and actionable.

Think of this as:

- **Now** – what the next focused work sessions should attack.
- **Next** – post-launch improvements that matter for day‑to‑day use.
- **Later** – deeper refactors, polish, and research.

---

## 1. Now (Release Focus – P0 / P1)

These are the things that make the current LLMC stack feel solid and intentional for you and for any future users.

### 1.0 Domain RAG – Technical Documentation Support (P0)

**Status:** 🟡 In Progress (Core parsing done, enrichment/graph pending)

**Goal:** Extend LLMC beyond code to handle technical documentation repositories with domain-aware chunking, embeddings, and enrichment.

**📄 Design:** [`legacy/SDD_Domain_RAG_Tech_Docs.md`](legacy/SDD_Domain_RAG_Tech_Docs.md)  
**📄 Research:** [`legacy/research/Extending LLMC to Domain-Specific Documents Research Finding.md`](legacy/research/Extending%20LLMC%20to%20Domain-Specific%20Documents%20Research%20Finding.md), [`legacy/research/Extending RAG to Non-Code Domains.md`](legacy/research/Extending%20RAG%20to%20Non-Code%20Domains.md)

**Key Changes:**
- New `[repository]` config section with `domain = \"code\" | \"tech_docs\" | \"legal\" | \"medical\" | \"mixed\"`
- `TechDocsExtractor` for heading-aware Markdown/DITA/RST chunking
- Section path prepending for context preservation
- Tech docs enrichment prompts (parameters, warnings, prereqs)
- Graph edges: `REFERENCES`, `REQUIRES`, `WARNS_ABOUT`

**Phases:**
- [x] Phase 1: Config schema (`[repository]` section, `domain` field) ✅ 
- [x] Phase 2: TechDocsExtractor implementation ✅ (2025-12-13, tests fixed 2025-12-16)
- [x] Phase 3: Enrichment schema + prompts ✅ (2025-12-15)
- [x] Phase 4: Graph edges (REFERENCES, REQUIRES, WARNS_ABOUT) ✅ (2025-12-16)
- [ ] Phase 5: CI smoke tests + validation on LLMC's own DOCS/

**Why This Matters:**
- Same 70-95% token savings for documentation repos
- Foundation for legal/medical domains later
- Already works with code repo docs (README, DOCS/)

**Effort:** ~20-30 hours | **Difficulty:** 🟡 Medium (6/10)

**See also:** `~/src/thunderdome/` - Dialectical autocoding orchestrator (separate project)

---

### ~~1.1 Ruthless MCP Testing Agent (RMTA)~~ ✅ DONE (Phase 1)

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

### ~~1.3 Documentation Accuracy Fix~~ ✅ DONE

**Completed:** Dec 2025

**Goal:** Remove or implement `llmc docs generate` - currently documented but doesn't exist.

**Summary:**
- ✅ Moved `llmc debug autodoc generate` to `llmc docs generate`
- ✅ Fixed CLI argument handling and DB path discovery
- ✅ Docs now match reality (command exists)
- ✅ Verified with `llmc docs status`

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

**⚠️ CURRENT STATE (2025-12-14):** Only stub backend implemented. The shell backend (`scripts/docgen_stub.py`) generates placeholder docs, not real LLM-generated documentation. Need to implement `backend = "llm"` option that uses enrichment chain (qwen3:14b+ with reasoning).

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


### 2.4 Interactive Configuration Wizard (P1)

**Status:** 🔴 Not started

**Goal:** Guide users through LLMC configuration with a friendly, interactive experience instead of requiring manual TOML editing.

**Problem:**
- Current `llmc repo register` creates a hardcoded config template
- Users have to manually edit `llmc.toml` to change models, Ollama URLs, etc.
- The TOML config structure is confusing (enrichment chains, routing, embedding profiles)
- Easy to misconfigure and get silent failures

**Proposed Solution:**
An interactive wizard triggered by `llmc repo register --interactive` or `llmc config wizard`:

1. **Ollama Discovery:**
   - Prompt for Ollama server URL (default: `http://localhost:11434`)
   - Ping the server to verify connectivity
   - Fetch available models via `/api/tags`
   - Display available models and let user select:
     - Primary enrichment model (smallest/fastest)
     - Optional fallback model (medium)
     - Optional final fallback model (largest)

2. **Model Recommendations:**
   - Suggest models based on popularity/capability (e.g., "qwen3:4b is fast, qwen3:8b is balanced")
   - Show model sizes to help users choose based on VRAM
   - Validate selected models are actually loaded in Ollama

3. **Embeddings Setup:**
   - Offer to use same Ollama server or different endpoint
   - Suggest common embedding models (jina, nomic-embed-text)
   - Test embedding generation works

4. **Generate Config:**
   - Write validated `llmc.toml` with user's choices
   - Show summary of what was configured
   - Offer to run `llmc repo validate` immediately

**CLI:**
```bash
llmc repo register . --interactive    # Full setup with wizard
llmc config wizard                    # Reconfigure existing repo
llmc config wizard --models-only      # Just update model selection
```

**Why P1:**
- Config errors are a major source of frustration (see "qwen2.5 instead of qwen3" bug)
- First-run experience is critical for adoption
- Reduces documentation burden

**Effort:** 8-12 hours | **Difficulty:** 🟡 Medium (5/10)

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


### ~~3.5.1 MCP Tool Exposure Architecture~~ ✅ DONE

**Completed:** 2025-12-16 (v0.7.0 "Trust Issues")  
**📄 SDD:** [`planning/SDD_MCP_Hybrid_Mode.md`](planning/SDD_MCP_Hybrid_Mode.md)  
**📄 AAR:** [`planning/legacy/AAR_MCP_WRITE_CAPABILITY_GAP.md`](planning/legacy/AAR_MCP_WRITE_CAPABILITY_GAP.md)

**Resolution:** Implemented MCP Hybrid Mode (`mode = "hybrid"`)

| Mode | Tools | Token Cost | Write | Security |
|------|-------|------------|-------|----------|
| **Classic** | 27 direct | ~10.5KB | ✅ Yes | Docker required |
| **Code Exec** | 4 bootstrap | ~1.9KB | ❌ No | Docker required |
| **Hybrid** ✨ | 6-7 promoted | ~2.5KB | ✅ Yes | Trusted (no Docker) |

**Key Insight:** Security is binary - either you trust it (hybrid) or you don't (Docker). Command allowlists/blocklists are theater. If you give an LLM bash, they can do anything.

**Current "Fix" (0.6.8):**
- Disabled code_execution mode entirely
- Uses classic mode with full 23 tools
- **This works but sacrifices 90% of the token savings that code_execution mode provides**

**The Actual Problem:**

1. **Anthropic's code_mode pattern** assumes tools are executed in a sandboxed subprocess
2. **MCP's value proposition** is giving LLMs access to the user's actual system
3. **These are philosophically incompatible** - you can't have both sandbox isolation AND real system access

**Research Questions:**

1. **Hybrid bootstrap_tools approach:**
   - Which tools are truly essential as direct MCP tools? (read, write, run_cmd?)
   - Which can safely be stub-gated? (RAG search, graph traversal, etc.)
   - Can we get 80% token savings with 100% capability?

2. **Security model for write tools:**
   - Is `allowed_roots` sufficient? (currently sandboxes to repo dir)
   - Should write tools require additional confirmation patterns?
   - Can we provide "audit trail" without full isolation?

3. **Alternative architectures:**
   - **Capability tokens:** Tools require per-session approval, not env vars
   - **Progressive disclosure:** Start with read-only, unlock write after first successful read
   - **Contract-based:** Agent declares intent, system validates against policy before execution

4. **Container trade-offs:**
   - How much UX friction does container isolation add?
   - Can we make `LLMC_ISOLATED=1` mode actually useful?
   - Docker vs nsjail vs Firejail for MCP server?

5. **Claude Desktop specific:**
   - What's the actual threat model for MCP on user machines?
   - Are we over-engineering security for a voluntary local install?
   - Would Anthropic ever allow write-capable MCP tools in claude.ai?

**Why This Matters:**

The current situation is unsustainable:
- Classic mode: Works but wastes tokens (23 tool definitions × ~1.8KB each = 41KB overhead)
- Code exec mode: Saves tokens but breaks write capability (the thing users actually want)

**Proposed Research Approach:**

1. **Phase 1: Hybrid experiment** (4-8 hours)
   - Add write tools to `bootstrap_tools` whitelist
   - Fix handler registration in `_init_code_execution_mode()`
   - Measure token savings vs classic (A/B test)

2. **Phase 2: Security audit** (8-16 hours)
   - Document actual attack vectors for MCP write tools
   - Evaluate `allowed_roots` protection adequacy
   - Propose additional safeguards if needed

3. **Phase 3: Architecture proposal** (8-12 hours)
   - Write ADR (Architecture Decision Record) for chosen approach
   - Define migration path for existing users
   - Update AGENTS.md with clear capability documentation

**Effort:** 20-36 hours research + implementation | **Difficulty:** 🔴 Hard (8/10)

**Why R&D, Not a Simple Fix:**

Web Opus was right: _"You aren't going to fix this with a bullshit patch."_

This is a fundamental architectural question about what MCP is for. The current code has both modes implemented but they represent two different philosophies:
- **Classic:** "Give Claude full access to the repo"
- **Code Exec:** "Claude can only observe, humans handle mutations"

We need to decide which philosophy we're actually building for, and design accordingly.


### ~~3.5 Repo Cleanup & Dead Code Removal~~ ✅ DONE
**Completed:** Dec 2025
**Goal:** Remove unused code, consolidate duplicate logic, and reduce technical debt.
**Summary:** Removed legacy scripts, consolidated core utilities, and cleaned up CLI entry points.


### ~~3.6 Remote LLM Provider Support for Enrichment~~ ✅ DONE
**Completed:** Dec 2025
**Goal:** Enable remote API providers (Gemini, OpenAI, Anthropic, Groq) in the enrichment cascade with production-grade reliability.
**Summary:** Implemented `RemoteBackend`, adapters for major providers, circuit breakers, rate limiting, and cost tracking.


### ~~3.7 RUTA & Testing Demon Army~~ → THUNDERDOME

**Status:** 🚚 Moved to separate repository

All multi-agent testing infrastructure (RUTA, Emilia, Testing Demons, Dialectical Autocoding) has been extracted to the **Thunderdome** project.

**📦 Repository:** `~/src/thunderdome/`

This includes:
- RUTA (Ruthless User Testing Agent)
- Emilia (Testing Orchestrator)
- All demon agents (Security, GAP, Performance, Chaos, etc.)
- Dialectical Autocoding protocols
- Agent dispatch infrastructure

**Why Separate:**
- Testing agents are repo-agnostic (can test any project, not just LLMC)
- Reduces LLMC repo size and complexity
- Allows independent versioning and development
- Thunderdome can orchestrate tests across multiple repos

---

### 3.10 Distributed Parallel Enrichment (R&D) 🔥 NEW

**Status:** 🔴 Research Required  
**Added:** 2025-12-14

**Problem:**
The current enrichment pipeline is **synchronous and single-host**:
- One span enriched at a time
- One Ollama server at a time  
- GPU sits idle between enrichment calls (model loading, network latency, DB writes)
- Multiple GPU systems in the homelab (Athena, desktop, laptop) can't work together

**Dave's Setup:**
- **Athena** (Strix Halo): iGPU with 96GB unified memory, can handle multiple concurrent requests
- **Desktop**: Dedicated GPU
- **Laptop**: Another GPU available
- Current utilization: ~40% on Athena during enrichment (lots of idle time)

**Proposed Architecture:**

```
                 ┌─────────────────────────────────────────┐
                 │           ENRICHMENT DISPATCHER         │
                 │  (async queue, work stealing, backpressure)  │
                 └───────────────┬─────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
   ┌─────────┐             ┌─────────┐             ┌─────────┐
   │ Athena  │             │ Desktop │             │ Laptop  │
   │ :11434  │             │ :11434  │             │ :11434  │
   │ (2-3    │             │ (1      │             │ (1      │
   │concurrent)│           │concurrent)│            │concurrent)│
   └─────────┘             └─────────┘             └─────────┘
```

**Key Design Decisions:**

1. **Async I/O:** Replace blocking `requests.post()` with `httpx.AsyncClient()` or `aiohttp`
2. **Work Queue:** `asyncio.Queue` with configurable concurrency per host
3. **Per-Host Concurrency:** Athena can handle 2-3 parallel requests, others 1
4. **Backpressure:** Don't overload slow hosts, let faster hosts pull more work
5. **Failure Isolation:** One host down shouldn't block the whole queue
6. **Result Aggregation:** Spans complete out-of-order, batch DB commits

**Configuration (llmc.toml):**
```toml
[enrichment.distributed]
enabled = true
max_concurrent_total = 5  # Global cap across all hosts

[[enrichment.distributed.hosts]]
url = "http://athena:11434"
max_concurrent = 3  # This host can handle 3 parallel
priority = 1        # Prefer this host

[[enrichment.distributed.hosts]]
url = "http://localhost:11434"
max_concurrent = 1
priority = 2

[[enrichment.distributed.hosts]]
url = "http://laptop:11434"
max_concurrent = 1
priority = 3
```

**Challenges:**

1. **Core Architecture Change:** Current `EnrichmentPipeline` is inherently synchronous
2. **DB Locking:** SQLite doesn't love concurrent writers (need WAL + careful transaction scope)
3. **Ordering:** Results come back out-of-order; current logging assumes sequential
4. **Error Handling:** Partial batch failures, retry logic, dead host detection
5. **Observability:** Which host enriched what? How to track T/s per host?

**Phased Implementation:**

| Phase | Description | Effort | Difficulty |
|-------|-------------|--------|------------|
| 0 | Async refactor of OllamaBackend (httpx) | 8-12h | 🟡 Medium |
| 1 | Multi-host config + dispatcher | 12-16h | 🟡 Medium |
| 2 | Per-host concurrency + backpressure | 8-12h | 🟡 Medium |
| 3 | Result aggregation + batch commits | 8-12h | 🔴 Hard |
| 4 | Monitoring + per-host metrics | 4-8h | 🟢 Easy |

**Total Effort:** 40-60 hours | **Difficulty:** 🔴 Hard (7/10)

**Why R&D:**
This goes against the core design assumption of "one enrichment at a time". The refactor touches:
- `tools/rag/service.py` - Main loop
- `tools/rag/enrichment_pipeline.py` - Pipeline orchestration
- `tools/rag/backends/ollama_backend.py` - HTTP client
- `tools/rag/database.py` - Transaction scope
- `llmc.toml` - New config schema

**Success Criteria:**
- [ ] 2-3x enrichment throughput on Athena alone (via concurrency)
- [ ] N hosts working in parallel without stepping on each other
- [ ] Graceful degradation when hosts go offline
- [ ] Per-host T/s metrics visible in TUI/logs

---

### ~~3.9 Architecture Polish & Tech Debt~~ ✅ DONE (2025-12-16)

**Status:** ✅ Complete  
**Added:** 2025-12-12 | **Completed:** 2025-12-16

Collection of architectural improvements identified during code review.

| Item | Status | Notes |
|------|--------|-------|
| ~~Break Import Cycle: rag ↔ rag_nav~~ | ✅ | Renamed `graph.py` → `graph_store.py` to avoid shadowing by `graph/` package |
| ~~Defer Heavy Imports~~ | ✅ | `DocgenOrchestrator`, `Database` now imported inside functions in `llmc/commands/docs.py` |
| ~~Dev Dependencies~~ | ✅ | Added `types-toml`, `types-requests`, `mypy`, `ruff`, `pytest-cov` to `[project.optional-dependencies.dev]` |
| ~~Path Safety Consolidation~~ | ✅ | Created `llmc/security.py` with `normalize_path()` and `PathSecurityError`. `inspector.py` now imports from there. |
| ~~Clean egg-info Artifacts~~ | ✅ | No stale artifacts found |
| Type Discipline in RAG | 🔴 Backlog | Run `mypy --strict tools/rag/` for baseline |
| Startup Health Checks | 🔴 Backlog | Add venv/mcp presence check in CLI entry |
| MCP Test Environment | 🔴 Backlog | Add Makefile target for `llmc_mcp/` tests |
| Event Schema Versioning | 🔴 Backlog | Define `EVENT_SCHEMA_VERSION` |
| Import Hygiene in docs.py | 🔴 Backlog | Exception chaining |
| ~~Create ARCHITECTURE.md~~ | ✅ | See `DOCS/ARCHITECTURE.md` |

**Summary:** Completed the high-impact items (import cycle, deferred imports, security consolidation, dev deps). Remaining items are pure polish.

---

### 3.11 Chat Session RAG (R&D) 💡 IDEA

**Status:** 🔵 Backlog (way at the back)  
**Added:** 2025-12-16

**Observation:** OpenAI and Anthropic's chat search both suck. They're basically keyword matching on titles, not semantic search over actual content.

**Idea:** Use LLMC's existing chunking/enrichment/embedding pipeline for chat history:
- Index past conversations (chunked by turns or topics)
- Semantic search: "That conversation where we discussed X"
- Inject relevant context from past sessions into bx agent

**Why It Would Work:**
- Same tech stack as code RAG: SQLite + embeddings + enrichment
- Conversations are just text spans with timestamps
- Could even link to code spans discussed ("when we fixed the MCP bug")

**Why It's Way Back:**
- Core RAG for code still has plenty of improvements to make
- Requires agent persistence story first
- Nice to have, not need to have

**Effort:** Unknown (R&D) | **Difficulty:** 🟡 Medium (conceptually simple, integration work)

---

## 4. How to use this roadmap

- When you start a work session, pull one item from **Now** and ignore the rest.
- When something from **Now** is truly finished, move its bullet (or a summarized version) into `ROADMAP_COMPLETED.md`.
- Periodically re‑shape **Next** and **Later** based on what is actually exciting or urgent.

The goal is not to track every tiny task, but to keep a **small, accurate map** of where LLMC is going *from here*.