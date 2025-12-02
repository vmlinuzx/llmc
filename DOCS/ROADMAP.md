# LLMC Roadmap

This roadmap focuses only on **active** work. Completed phases and big wins are moved to `ROADMAP_COMPLETED.md` so this file stays short and actionable.

Think of this as:

- **Now** – what the next focused work sessions should attack.
- **Next** – post-launch improvements that matter for day‑to‑day use.
- **Later** – deeper refactors, polish, and research.

---

## 1. Now (Release Focus – P0 / P1)

These are the things that make the current LLMC stack feel solid and intentional for you and for any future users.



### 1.2 Enrichment pipeline tidy‑up

**Goal:** Bring the enrichment pipeline closer to the design in the docs without over‑engineering.

**📄 Design:** [`planning/SDD_Enrichment_Pipeline_Tidy.md`](planning/SDD_Enrichment_Pipeline_Tidy.md)

**Summary:**
- Extract `OllamaBackend` as proper `BackendAdapter` implementation
- Create `EnrichmentPipeline` class to orchestrate: pending spans → router → cascade → DB writes
- Wire `service.py` to use pipeline directly (no more subprocess to 2,271-line script)
- Sets foundation for remote providers (3.6)

**Phases:** 3 phases, ~4-6 hours total
| Phase | Effort | Deliverable |
|-------|--------|-------------|
| Extract OllamaBackend | 1-2h | `enrichment_adapters/ollama.py` |
| Create EnrichmentPipeline | 2-3h | `enrichment_pipeline.py` |
| Wire into Service | 1-2h | Direct calls, no subprocess |

### 1.3 Surface enriched data everywhere it matters

Most of the enrichment data plumbing exists (DB helpers, graph merge, nav tools), but this keeps it honest:

- Verify that:
  - `tools.rag_nav` tools (`search`, `where-used`, `lineage`) include enriched summaries where appropriate.
  - The TUI’s inspector view can show enrichment summaries and key metadata for a span/entity.
- Add or update tests to assert:
  - Enriched fields are present in the JSON envelopes returned by nav tools.
  - A missing or stale enrichment fails gracefully instead of crashing a tool.
- **Completed (Nov 2025):** Ensured integration tests (P0 acceptance) properly reflect the enrichment schema, allowing tests to verify that enrichment data is attached correctly.

### 1.4 Clean public story and remove dead surfaces

**Goal:** Reduce confusion and maintenance by cutting old interfaces.

- Tighten the README and top‑level docs:
  - Clearly state the supported entrypoints:
    - `llmc-rag`, `llmc-rag-nav`, `llmc-rag-repo`, `llmc-rag-daemon/service`, `llmc-tui`.
  - Call out what LLMC does *not* try to be (no hosted SaaS, no magic auto‑refactor).

### 1.6 System Friendliness (Idle Loop Throttling)

**Goal:** Prevent the daemon from burning CPU when there is no work to do.

**📄 Design:** [`planning/SDD_Idle_Loop_Throttling.md`](planning/SDD_Idle_Loop_Throttling.md)

**Summary:**
- Set process nice level (+10) so daemon doesn't compete with your IDE
- Track "work done" per cycle to detect idle state  
- Exponential backoff when idle (180s → 360s → 720s → ... → 30min cap)
- Instant reset to normal interval when changes detected
- Interruptible sleep for responsive signal handling

**Effort:** 2-3 hours | **Difficulty:** 🟢 Easy

### 1.7 MCP Daemon with Network Transport

**Goal:** Enable external systems (Codex, Gemini, custom agents) to connect to LLMC's MCP server over HTTP.

**📄 Design:** [`planning/SDD_MCP_Daemon_Architecture.md`](planning/SDD_MCP_Daemon_Architecture.md)

**Summary:**
- Add HTTP/SSE and WebSocket transport modes (MCP SDK already has the plumbing)
- API key authentication middleware for security
- Proper daemon management with pidfiles and signal handling
- CLI wrapper (`llmc-mcp start/stop/status/logs`)
- Preserves existing stdio transport for Claude Desktop (no breaking changes)

**Phases:** 6 phases, ~15-22 hours total
| Phase | Difficulty |
|-------|------------|
| HTTP + SSE Transport | 🟡 Medium |
| WebSocket Transport | 🟢 Easy |
| Auth Middleware | 🟢 Easy |
| Daemon Manager | 🟡 Medium |
| CLI Wrapper | 🟢 Easy |
| Testing & Docs | 🟢 Easy |

### 1.8 MCP Tool Expansion

**Goal:** Expose critical navigation and inspection tools through MCP.

- **Completed (Dec 2025):** Added `rag_where_used`, `rag_lineage`, `inspect`, and `rag_stats`.
- Remaining observability tools (P1):
  - `rag_plan` - Heuristic retrieval planning for queries.
- Update code execution stubs to include new tools (Verified: automatic via `TOOLS` list).

---

## 2. Next (Post‑Launch P1)

These are things that make LLMC nicer to live with once the core system is “good enough”.

### 2.1 Productization and packaging

**Goal:** Turn LLMC from “a pile of scripts” into “a thing you can install and run”.

- Move toward a single `llmc` CLI entrypoint that wraps the main flows:
  - `llmc init` (bootstrap a repo and `.llmc` workspace).
  - `llmc index` / `llmc enrich` / `llmc build-graph`.
  - `llmc service start|stop|status`.
- Reduce `bash -> python` chains where possible to cut startup overhead.
- Make sure a new clone can do:
  - `pip install -e .`
  - `llmc init && llmc index && llmc-tui`
  with minimal extra steps.

### 2.2 Polyglot RAG support

**Goal:** Make the schema graph and RAG story work across more than just Python.

- Extend `SchemaExtractor` to handle at least one non‑Python language end‑to‑end (JS/TS is a good first target):
  - Tree‑sitter integration for parsing.
  - Entity and relation mapping that matches the existing graph model.
  - Tests against a real non‑Python sample repo.
- Update docs to describe language support explicitly (Python: full, JS/TS: beta, others: TBD).

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

### 3.4 Multi-Agent Coordination & Anti-Stomp

**Goal:** Enable multiple agents to work concurrently without stomping on each other's changes.

- Research and design coordination mechanisms:
  - File-level locking with claim/release protocol.
  - Conflict detection (detect overlapping edits before commit).
  - Work queue / ticketing system for task distribution.
  - Lint-aware coordination (prevent concurrent edits that break linting).
- Implement anti-stomp primitives:
  - `claim_file(path, agent_id, timeout)` - Reserve file for editing.
  - `release_file(path, agent_id)` - Release claim.
  - `check_conflicts(path, agent_id)` - Detect if file changed since claim.
  - Automatic release on timeout or agent disconnect.
- Add coordination layer to MCP server:
  - Track active claims in SQLite (`.llmc/agent_claims.db`).
  - Expose coordination tools via MCP (`claim_file`, `release_file`, etc.).
  - Integrate with file write operations (auto-claim before edit).
- Testing strategy:
  - Simulate 3+ concurrent agents editing different files.
  - Simulate conflict scenarios (same file, overlapping lines).
  - Verify lint passes after concurrent edits.
- **Prior art:** Flat ticketing system (worked up to 3 agents with occasional lint issues).
- **Success criteria:** 5+ agents working concurrently with zero stomps and clean lints.

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