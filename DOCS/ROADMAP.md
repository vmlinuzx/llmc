# LLMC Roadmap

This roadmap consolidates the previous `ROADMAP.md`, `Roadmap.md`, and `ROADMAP_P1_Tool_Contract_Self_Describing_Tools.md` into a single, canonical document for this repo.

---

## Near-Term TODOs (Next Roadmap Warrior)

- Draft `DOCS/TOOLS_DESKTOP_COMMANDER.md` as the authoritative tool manifest (MCP-style schemas) for `llmc-rag-*` and friends.
- Seed a stub `tools/rag/enrichment_backends.py` with types and a skeleton API (`Backend`, `BackendChain`, `load_for_repo`), no behavior yet.
- Seed a stub `tools/rag/enrichment_pipeline.py` with a no-op `run_pipeline(...)` that simply returns spans, matching current behavior.
- Add `DOCS/RAG_Enrichment_Hardening.md` as a short operator guide for timeouts, health checks, and log locations.

---

## Phases

- **P0 – Immediate**: critical bugs, auth, deploy blockers.
- **P1 – Core**: main feature set, happy-path flows.
- **P2 – Quality**: performance, DX polish, observability, docs.
- **P3 – Nice-to-have**: experiments, stretch goals.

---

## Current Priorities

- **P0: Enrichment Data Integration (DB → Graph → API)**
  IMPLEMENTING - Close the loop between the `.rag/index_v2.db` enrichment store, the schema graph builder, and the public `tools.rag` API so that enriched summaries/evidence actually surface in user-facing results.
  IMPLEMENTING - Add a robust mapping layer from `enrichments.span_hash`/`spans` (file path + line range) to `SchemaGraph.entities[*]` and merge enrichment fields into `Entity.metadata` during graph build/export.
  IMPLEMENTING - Replace the current `tool_rag_search` / `tool_rag_where_used` / `tool_rag_lineage` stubs with thin adapters over the real search + enrichment pipeline, wired to the graph and database.
  - Ship end-to-end tests that assert: (1) enrichments exist in the DB, (2) graph entities expose enrichment metadata, and (3) the public API returns enriched results instead of empty lists.


  ### Phase 1 – DB / FTS foundation (this patch)
 Consider embedding model converted to matryoshka support 

  - Add a typed enrichment projection (`EnrichmentRecord`) that represents joined `spans` + `enrichments` rows.
  - Implement DB helpers to join spans and enrichments and expose them as typed records.
  - Add an optional FTS5 surface over enrichment summaries to support text search on enrichment content.
  - Add unit tests for the DB helpers and FTS plumbing only.
  - No graph or public tool changes in this phase.

  ### Phase 2 – Graph enrichment + builder orchestration

  - Extend `Entity` in `tools.rag.schema` with stable location fields (`file_path`, `start_line`, `end_line`) alongside the existing `id`/`path`.
  - Implement `build_enriched_schema_graph(repo_root)` that uses the new DB helpers to attach enrichment metadata onto `SchemaGraph.entities[*]`.
  - Implement `build_graph_for_repo(repo_root, require_enrichment=True)` and wire it into the RAG CLI / graph export path.
  - Add tests that assert enriched metadata appears in `.llmc/rag_graph.json` for repos with populated enrichment DBs.

  ### Phase 3 – Public RAG tools over DB + graph

  - Implement real `tool_rag_search`, `tool_rag_where_used`, and `tool_rag_lineage` using:
    - DB FTS helpers for query → span/symbol resolution.
    - `GraphStore` + enriched entities for structural and enrichment context.
  - Wrap responses in `RagResult` / `RagToolMeta` envelopes so MCP/CLI callers get consistent metadata about source, freshness, and enrichment.
  - Add integration tests for the MCP/CLI contracts that assert non-empty, enriched results for realistic queries.

  ### Phase 4 – CLI / MCP wiring + observability

  - Add CLI commands for `search` / `where-used` / `lineage` that call the new `tools.rag` entrypoints, plus a command to rebuild FTS indexes.
  - Add a debug CLI (counts, sample records) to inspect enrichment coverage, graph attachment rate, and FTS health.
  - Wire the tools into the MCP server and update docs so upstream agents (Desktop Commander, Codex wrappers) can rely on the enriched RAG surface.

- **P0: Critical Code Quality - Duplicate Function Definitions in schema.py**
  **STATUS**: CRITICAL CODE SMELL - `tools/rag/schema.py` has THREE definitions of `extract_schema_from_file()` at lines 308, 337, and 366
  **WHY**: Python silently overrides earlier definitions. Only the last one (line 366) is actually used, but this creates maintainability nightmares and suggests copy-paste errors during development.
  **FIX**: 
  - Remove duplicate definitions at lines 308 and 337
  - Verify line 366 implementation is correct and complete
  - Add linting rules to catch duplicate function definitions
  - Audit entire codebase for similar issues
  **IMPACT**: Low runtime impact (last definition wins), but HIGH maintenance risk and code smell

- **P0: Graph Edge Extraction & Call Graph Analysis**
  **STATUS**: CRITICAL - Currently have 2,394 nodes but 0 edges. Graph traversal is completely non-functional.
  **WHY**: This is the core differentiator for LLMC - architectural understanding via call graphs. Without edges, we're just doing fancy grep with embeddings.
- **P0: Graph Edge Extraction & Call Graph Analysis**  
  **STATUS**: ✅ FIXED (2025-11-19) - Graph has 9,779 edges! Bug was in loader, not extractor.  
  **ROOT CAUSE**: `tools/rag_nav/tool_handlers._load_graph()` was looking for `data["edges"]` or `data["schema_graph"]["relations"]` but `SchemaGraph.to_dict()` saves as top-level `data["relations"]`  
  **FIX APPLIED**: Modified `_load_graph()` to check `data.get("relations")` first  
  **VERIFICATION**: Graph now loads: 2,394 nodes, 9,779 edges (CALLS relationships working!)  
  **CURRENT LIMITATION**: Only Python files have schema extraction. Other languages return empty ([], []).
  
  ### Phase 1 – Enable Graph Traversal Queries (NOW UNBLOCKED - edges working!)
  - Implement `tool_rag_callers(entity_id)` - reverse call graph lookup using the 9,779 edges
  - Implement `tool_rag_dependencies(entity_id)` - full dependency tree traversal
  - Implement `tool_rag_impact_analysis(entity_id)` - "if I change this, what breaks?"
  - Add graph traversal to TUI for visual exploration
  - Add edge type extraction for `imports` (currently only have `calls` and `extends`)
  
  ### Phase 2 – Multi-Language Support (Python-only currently)
  - JavaScript/TypeScript: Use tree-sitter or similar AST parser
  - Java: Import/dependency extraction
  - Go: Module and package relationships
  - C/C++: Header includes and linkage
  - Universal fallback: Regex-based import detection for unsupported languages (Ada, Fortran, COBOL, etc)
  
  ### Phase 3 – Advanced Graph Features
  - Data flow analysis: "how does data move through this system?"
  - Architectural layers: Detect API → service → data patterns
  - Cyclic dependency detection and warnings
  - Dead code identification via graph reachability
  - Hotspot detection: Most-called/most-depended-on entities

- **P1: RAG Freshness Gate + Safe Local Fallback**
  - Add a freshness gate in front of RAG so tools only use RAG when slice state is known-good, otherwise fall back automatically to local filesystem/AST-based logic.
  - Ensure callers (Codex, Claude, Desktop Commander, future GUIs) never have to care whether RAG is in play; they always get correct results plus metadata about source and freshness.

- **P1: Tool Contract & Self-Describing Tools (Desktop Commander)**
  - Define a single, authoritative manifest of tools LLMC is allowed to use.
  - Make that manifest visible in docs and at runtime (especially on invalid commands) so models can self-correct instead of flailing.

- **P1: New Repo Hygiene & RAG Enablement**
  - Keep this repo minimal and professional (no duplicate docs, clear contracts/agents, clean DOCS tree).
  - Re-enable RAG in this repo once basic contracts, tools, and sidecars are stable.

---

## Quality & Hardening Roadmap (P11)

### 0. Definition of “Good Enough for Government Work”

The system is “good enough” when:

- There are no obvious foot-guns around:
  - Path traversal.
  - SQL injection.
  - Subprocess misuse.
- Core surfaces return a structured error envelope (e.g., RagToolMeta-style).
- P0 surfaces (security, DB, registry, router/daemon) all have direct tests.
- `bare except:` and undefined-name issues are cleaned up.
- CI can run with a single command on a fresh clone with:
  - A clean run.
  - No flakiness.
- Basic runbooks exist for:
  - “Service won’t start.”
  - “Index is corrupted.”
  - “RAG looks wrong.”

The following phases describe how to get there incrementally.

### Phase 1 – Red-Risk Hardening (Security & Data Integrity)

**1.1 Filesystem & path safety**

- Implement a shared `safe_resolve(base, user_path)` helper that:
  - Resolves and normalizes paths.
  - Enforces “must stay under base”.
- Use it everywhere untrusted paths come in (registry, repo roots, workspaces).
- Replace the current “path traversal vulnerability demo” tests with:
  - Real “this now fails safely” tests, or
  - Strict `xfail` markers until fixed.

**1.2 Database & SQL safety**

- Audit all SQL sites; enforce parameterized queries for any user/config text.
- Centralize DB writes in a small API surface.
- Add tests that try injection via:
  - Paths, filenames, languages, descriptions.
- Assert that:
  - Schema remains intact.
  - Malicious strings are stored as data, not executed.

**1.3 Subprocess & command exec safety**

- Inventory all subprocess usage.
- Enforce rules:
  - No `shell=True` with untrusted input.
  - Always pass argument lists, not shell strings.
- Add tests:
  - Mock `subprocess` and assert `shell=False` and list args in real code paths.

**1.4 Config & registry validation**

- Define schemas for config/registry files (required keys, types, enums).
- Implement `validate_config` / `validate_registry_entry`.
- Add tests for missing keys, wrong types, invalid paths → predictable exceptions / error responses.

### Phase 2 – Structured Error Handling & Recovery

**2.1 Standard error envelope**

- Finalize meta schema (status, `error_code`, `message`, `source`, `freshness_state`).
- Apply to:
  - RAG tools (search / where-used / lineage).
  - CLI/daemon APIs.
- Tests for forced failures should assert:
  - `status="ERROR"`.
  - Stable `error_code`.
  - Useful, non-leaky `message`.

**2.2 Network & LLM provider failures**

- Map provider failures to internal codes:
  - Timeouts, connection errors, 429, 4xx auth, 5xx.
- Implement retry/backoff for transient errors; fast-fail for bad requests.
- Mock-based tests to verify:
  - Retry behavior.
  - Final structured errors.

**2.3 DB corruption & migration**

- On DB open:
  - Integrity + schema-version checks.
- On mismatch:
  - Attempt migration, otherwise return clear error with next steps.
- Tests with corrupted/old/missing-schema DBs to exercise these paths.

**2.4 Daemon & workers**

- Job-level error containment:
  - One job failing must not bring down the whole daemon.
- Tests:
  - Fake job that always throws → daemon survives, failure visible via status/logs.

### Phase 3 – Test Suite Hygiene & Signal

**3.1 Convert spec-tests into real tests**

- Triage `tests/test_error_handling_comprehensive.py`:
  - Convert keepers into real tests that call LLMC code.
  - Mark “known bug / future behavior” with strict `xfail`.
  - Drop pure stdlib demos from CI.
- Replace `try: assert True` patterns with:
  - `pytest.raises(...)`, or
  - Assertions on results/envelopes.

**3.2 Lint & style as a gate**

- Fix all:
  - `bare except:` (E722).
  - Undefined names (F821).
- Add a minimal Ruff gate in CI for those rules only.
- Optionally expand lint rules later once red risks are under control.

**3.3 Smoke / regression tests**

- Add “tiny repo” smoke tests:
  - Index, search, where-used, plan on fixtures.
- Assert:
  - Exit code 0.
  - No tracebacks.
  - Basic shape of output is correct.
- Tag slow/perf checks appropriately.

### Phase 4 – Observability & Ops

**4.1 Logging & metrics**

- Standardize error logging fields:
  - Component, error code, message, context.
- Tests:
  - Use `caplog` to assert logs for key failure paths.

**4.2 Operator runbooks**

- Write short runbooks for:
  - Index corrupted/missing.
  - Service won’t start.
  - RAG results stale/wrong.
- Each runbook should include:
  - Symptoms.
  - Log hints.
  - Diagnostics and safe remediation steps.

**4.3 Security/compliance checklist**

- Simple checklist for releases:
  - Path traversal protections tested.
  - DB/subprocess patterns verified safe.
  - Errors/logs do not leak secrets.
- Run before major releases; keep in the repo.

### Phase 5 – Stretch / Nice-to-Haves

- Chaos-style tests for indexing/daemon (kills, network flakiness).
- Automated test-gap reports over time.
- Optional dependency/security scanners wired into CI.

**Suggested execution order (for Cheap, Lazy, ADHD Dave™):**

1. Phase 1 – Path/DB/subprocess/config hardening (maximum risk reduction per line of code).
2. Phase 2 – Standard error envelopes + network/DB failure handling.
3. Phase 3 – Clean test suite + lint gate + smoke tests.
4. Phase 4 – Logs and runbooks (so Future You doesn’t hate Past You).
5. Phase 5 – Only if you’re feeling spicy.

---

## Recently Completed (Highlights)

These are carried forward from the previous roadmap and kept as high-signal accomplishments:

- **Template & RAG wiring**
  - Pipe RAG planner output into wrappers so Codex/Claude/Gemini consume indexed spans automatically.
  - Lock MVP stack and scope for template-builder UX.

- **RAG daemon correctness**
  - Fix daemon enrichment to use the real enrichment pipeline instead of fake summaries.
  - Verify enriched spans, routing behavior, and logging/metrics are all producing real data.

- **Architecture investigations**
  - Investigate RAG integration layers, confirm wrapper-owned architecture, and identify duplication (`rag_plan_snippet` variants).

- **RAG Nav P9–P10: search quality & graph indices**
  - Added configurable reranker weights via `.llmc/rag_nav.ini` and `RAG_RERANK_W_*` env vars, with safe normalization defaults.
  - Introduced lightweight canary/search evaluation harnesses (`tools.rag.canary_eval`, `tools.rag.eval.search_eval`) and sample canary query sets.
  - Implemented graph-indexed where-used and lineage over `.llmc/rag_graph.json` (P10a/P10b), wired through the Context Gateway with graceful local fallbacks.

---

## Backlog (Condensed)

This section is a trimmed, de-duplicated version of the prior backlog; items remain small (1–3 days) and implementation details live in the code/docs they reference.

### RAG & Context Quality

- **Polyglot RAG Support (JS/TS/Go/etc.)**
  - **Context:** Currently, `tools/rag/schema.py` hardcodes `if lang == "python": ...` and only extracts AST from `.py` files. `tools/rag/indexer.py` supports other languages for raw span chunking, but the **Graph Builder** ignores them, leading to "No source files found" errors and empty graphs for non-Python repos (e.g., `livecaptions_advanced`).
  - **Goal:** Expand `SchemaExtractor` to support `tree-sitter` (or similar) for JavaScript, TypeScript, Go, and Rust so that the Entity Graph covers the full stack.
  - **Implementation:**
    - Integrate `tree-sitter` python bindings.
    - Implement `JavaScriptSchemaExtractor`, `GoSchemaExtractor`, etc.
    - Update `build_graph_for_repo` to scan for these extensions.

- Complete schema-enriched/graph-style RAG integration and validation benchmarks.
- Standardize RAG architecture across wrappers using a shared helper (e.g., `scripts/rag_common.sh`).
- Harden freshness automation (cron-friendly refresh wrapper + docs/locks/logs).
- Introduce AST-driven chunking for key languages (Python, TS/JS, Bash, Markdown).
- Add deterministic enrichment fallback: when RAG execution fails due to stale/out-of-date indexes for non-context queries, attempt a local/AST-based enrichment path before surfacing a structured error to callers.

### Tooling & Templates

- Polish template builder experience and clean template repositories (keep only what belongs in context zips).
- Ship a spec compressor and wiring to downstream orchestration (e.g., Architect → Compressor → Beatrice).
- Add guardrails for spec brevity and token budgets before dispatching to heavy models.

### Performance, Observability & Ops

- Establish a performance profiling baseline and minimal error tracking.
- Add lightweight semantic cache manager for answers/chunks with simple metrics.
- Automate RAG/sidecar regeneration as part of enrichment flows.
- Improve log rotation and metrics sinks as needed for long-running services.

### Post-MVP / Stretch

- Re-architect sidecar system to store summaries in RAG instead of loose repo files.
- Consolidate enrichment/runtime flags into a shared, documented configuration.
- Explore GUI tooling for compressor/configuration once the core flows are stable.

### Epic: Productization & Speed (The "Defuckingscriptify" Pass)

**Goal:** Transform LLMC from a collection of hacker scripts into a fast, installable Python package (`pip install llmc`).

**Objectives:**
1.  **Eliminate Script Overhead:** Replace `bash -> python` chains with direct Python API calls to remove interpreter startup latency (50-200ms per call).
2.  **Unified Configuration:** Replace scattered env vars with a single `llmc.toml` (e.g., LLM providers, enabled features).
3.  **Single Entrypoint:** Consolidate `rag_plan_helper.sh`, `qwen_enrich_batch.py`, etc. into a single `llmc` CLI.
4.  **Distribution:** Make the system installable and usable with a simple `llmc init && llmc start`.
5.  **Interactive TUI Polish:** Enhance the 6-panel dashboard into a fully interactive application with navigation stacks, configuration editing, and live analytics visualizations (Post-MVP).

---

## P1 – RAG Freshness Gate & Safe Local Fallback

### TL;DR

Introduce a **freshness gate** in the LLMC RAG stack so that:

- RAG is only used when we **know** the repo slice is fresh.
- When RAG is stale/unknown, tools **automatically fall back** to local filesystem/AST-based logic.
- Callers never have to care whether RAG is in play; they always get correct results plus metadata (`source`, `freshness`).

This prevents “RAG lied to me” failures during refactors and upgrades and makes RAG a **performance/quality bonus**, never a single point of failure.

### Problem / Why

- Today the RAG DB is assumed correct if it exists; tools and CLI layers do not check freshness.
- When the daemon is down, mid-upgrade, or behind, tools still query a stale DB and models see a view of the repo that no longer matches reality.
- This silently breaks refactors, symbol/where-used queries, and trust in LLMC behavior.

### Goals

1. **Freshness metadata** for each repo/slice:
   - Track `repo_id`, `slice_key`, `index_state`, `last_indexed_at`, `last_indexed_git_head`, `schema_version`.
   - Support states like `fresh`, `stale`, `rebuilding`, `unknown`.
2. **Gateway-based routing**:
   - A single context gateway decides between RAG and local tooling.
   - When fresh → use RAG and tag responses `source = "rag"`, `freshness = "fresh"`.
   - When not fresh/unknown/error → fall back to local and tag responses with appropriate `*_fallback` freshness.
3. **Operational safety**:
   - RAG upgrades, daemon restarts, and schema migrations must not brick tools.
   - Worst case behavior must be “no RAG” correctness.

### Scope / Implementation Notes

- Add/update a small metadata store (table or sidecar file) that tracks slice state and last indexed git commit.
- Implement a `context_gateway` module which:
  - Wraps all RAG calls.
  - Performs a fast freshness check on each request.
  - Handles RAG failures by logging and falling back to local tools instead of surfacing raw errors.
- Reuse existing grep/AST/local tools for the initial fallback path—correctness first, performance later.

### Acceptance Criteria (Condensed)

- Metadata is updated on index job start/success/failure and exposes the fields listed above.
- All RAG-consuming tools call through a single gateway.
- When metadata says `fresh`, RAG is used; otherwise local tools are used and responses are tagged with meaningful freshness values.
- At least one end-to-end scenario demonstrates “RAG behind by N commits → refactor/where-used is still correct via local path.”
- Docs clearly explain RAG as a best-effort accelerator with freshness/fallback semantics and how maintainers can inspect/override state.

---

## P1 – RAG Navigation & Context Gateway

### Task 1 – RAG Nav Index Status Metadata

**Status:** COMPLETED (metadata + helpers + tests are in place).

**Goal:** Add a minimal, durable status layer so tools can know whether the RAG graph/index is fresh, stale, rebuilding, or broken.

**What it delivers:**

- New package `tools.rag_nav` with:
  - `IndexStatus` dataclass and `IndexState` enum (`fresh` | `stale` | `rebuilding` | `error`).
  - JSON status file at `${REPO_ROOT}/.llmc/rag_index_status.json`.
  - Safe helpers `load_status` / `save_status` with atomic writes.
- Unit tests for status read/write and corrupt-file handling.
- Docs describing the status schema and usage.

**Why it matters:** This becomes the single source of truth for freshness and is the foundation for the Context Gateway and safe fallbacks.

### Task 2 – Graph Builder + `llmc-rag-nav` CLI (build + status)

**Status:** COMPLETED (schema-enriched graph v2 + CLI).

**Goal:** Be able to manually build the schema-enriched graph and status for a repo, with zero daemon/MCP wiring.

**What it delivers:**

- `tools.rag_nav.tool_handlers.build_graph_for_repo(repo_root)` that:
  - Builds graph artifacts (using existing RAG primitives).
  - Writes `${REPO_ROOT}/.llmc/rag_graph.json`.
  - Writes `IndexStatus` with `index_state="fresh"`, timestamp, commit, and schema version.
- `tools.rag_nav.cli` with:
  - `llmc-rag-nav build-graph --repo .`
  - `llmc-rag-nav status --repo . [--json]`
- Fixture repo and tests verifying graph and status generation.

**Why it matters:** Provides a debuggable, standalone graph builder before wiring anything into the daemon—easy to trust, easy to revert.

### Task 3 – RAG Where-Used / Lineage / Search Handlers (RAG-only)

**Status:** COMPLETED (graph-backed handlers with grep fallback).

**Goal:** Implement core where-used, lineage, and code search operations using the graph/index only, callable via CLI (and later MCP). No freshness/fallback logic yet.

**What it delivers:**

- Extended `tools.rag_nav.models` with:
  - `SnippetLocation`, `Snippet`.
  - Result types: `SearchResult`, `WhereUsedResult`, `LineageResult` with `items`, `truncated`, `source`, `freshness_state`.
- Handlers in `tools.rag_nav.tool_handlers`:
  - `tool_rag_search(...)`
  - `tool_rag_where_used(...)`
  - `tool_rag_lineage(...)`
  - All reading `${REPO_ROOT}/.llmc/rag_graph.json` and returning structured hits.
- CLI subcommands:
  - `llmc-rag-nav search`
  - `llmc-rag-nav where-used`
  - `llmc-rag-nav lineage`
- Tests asserting basic correctness and truncation behavior.

**Why it matters:** This is the actual “brain” of the where-used/lineage feature. Once this exists, everything else is just routing and plumbing.

### Task 4 – Context Gateway + Freshness/Fallback Routing

**Status:** PARTIAL / DEFERRED – basic gateway + routing are implemented and in use; additional end-to-end freshness/fallback scenarios are tracked in the Backlog and will be finished when they become pressing.

**Goal:** Add a small Context Gateway that decides whether to use RAG or local fallback based on `IndexStatus`, and ensure every tool result is tagged with `source` and `freshness_state`.

**What it delivers:**

- New module `tools.rag_nav.gateway` with:
  - `Intent` enum (`search`, `where_used`, `lineage`, `status`).
  - `classify_intent(text)` (keyword-based).
  - `RouteDecision` with `use_rag`, `freshness_state`, `status`.
  - `route(intent, repo_root)` using `IndexStatus` (and optionally git HEAD) to decide freshness.
- Updated handlers in `tools.rag_nav.tool_handlers` that:
  - Route through the gateway.
  - Call RAG path when `use_rag=True` (`source="RAG_GRAPH"`).
  - Call simple local fallback / “not available” when `use_rag=False` (`source="LOCAL_FALLBACK"`).
- Tests for routing behavior (fresh vs. stale vs. unknown).

**Why it matters:** This is the safety switch that prevents you from hitting stale RAG data and silently corrupting answers. It’s also the hook point for future MCP tools, TUIs, and daemons.

---

## P1 – Tool Contract & Self-Describing Tools

This section subsumes the prior `ROADMAP_P1_Tool_Contract_Self_Describing_Tools.md`.

### TL;DR

Instead of jumping straight to dashboards, this P1 makes LLMC *much* smarter about what it can and can’t do by:

1. Defining a **single, authoritative tool contract** (manifest) for Desktop Commander tools LLMC should use.
2. Making that manifest visible to RAG (docs) and at runtime (on invalid commands).
3. Tracking invalid tool usage lightly so we can see whether changes reduce flailing.

### Problem

- LLMC and attached models often **guess** tool/command names (`query` vs `search`).
- Bad guesses currently produce opaque errors instead of teaching the model what is actually available.
- There is no single documented source of truth that lists:
  - which tools LLMC is allowed to use,
  - what parameters they expect,
  - and how dangerous they are.

### Goals

1. **Tool manifest (contract)**
   - Define a manifest (e.g., `DOCS/TOOLS_DESKTOP_COMMANDER.md`) listing the tools LLMC may use.
   - For each tool capture: `name`, `description`, `parameters` (JSON-schema style), `side_effect` (`read`/`write`/`process-kill`/`config`), and `danger_level` (`low`/`medium`/`high`).
2. **Self-describing errors**
   - Wrap key entrypoints so that unknown commands / bad parameters return:
     - A short human message.
     - A compact view of the manifest (tool names, descriptions, top-level parameters, side-effect, danger level).
   - This gives the model a concrete menu to recover from invalid calls.
3. **Lightweight metrics**
   - Track invalid tool usage (e.g., `tool_invalid_calls`, `tool_invalid_first_name`, `tool_invalid_recovered`).
   - Use ad-hoc analysis (jq/python) to confirm the change reduces thrashing; no full dashboard needed.

### Scope / Implementation Notes

- Begin with 5–15 core tools LLMC should touch; treat the manifest as a whitelist, not a mirror of all Desktop Commander capabilities.
- Ensure the manifest is indexed by RAG so planning prompts and “what can I do?” questions can discover it.
- Add minimal logging around invalid tool usage in existing run logs or a small companion log file.

### Risks / Considerations

- **Manifest drift**: keep the manifest updated as tools evolve; prefer smaller, high-signal sets of tools.
- **Dangerous tools**: clearly label anything with strong side effects and consider leaving the most dangerous tools out of the manifest.
- **Scope creep**: keep this effort focused on doc + invalid-command behavior + light metrics; dashboards and full observability can wait.

### Milestones

1. **M1 – Tool manifest drafted and linked**
   - `DOCS/TOOLS_DESKTOP_COMMANDER.md` created and referenced from the contracts/docs.
2. **M2 – Invalid command handler wired**
   - Core entrypoints emit manifest-guided help on invalid commands; smoke-tested with manual and bomb-test-style runs.
3. **M3 – Metrics emitting & validated**
   - Invalid-tool metrics are written; one ad-hoc analysis validates data quality and confirms the manifest is helping.

---

## Post-MVP – Enrichment Backends Module

The current enrichment pipeline wires backend decisions (Ollama hosts, gateway usage, tiers) via environment variables and ad-hoc logic inside `qwen_enrich_batch.py`. This works, but it buries the “magic” in a single script and makes it hard to reason about or reuse.

### TL;DR

Extract enrichment backend orchestration into a dedicated `tools.rag.enrichment_backends` module that:

- Owns the full backend chain configuration (hosts, tiers, gateway vs. local).
- Encapsulates health checks, failover rules, and timeouts.
- Exposes a small, testable API for “get me an LLM call for this span.”

### Goals

1. **Single source of truth** for enrichment backends:
   - Represent all backends (ollama hosts, gateway profiles, future cloud providers) as structured config (likely TOML + env overrides).
   - Make the chain discoverable from RAG/agents (“what LLMs are in play for this repo?”).
2. **Pluggable orchestration logic**:
   - Move host selection, tier routing, and failover rules into one module instead of scattering them across scripts.
   - Keep the interface small: e.g., `choose_backend(span_meta) -> BackendConfig`.
3. **Observability-friendly behavior**:
   - Standardize heartbeat, health-check, and error reporting fields for logs/metrics.
   - Make it easy to instrument “which backend handled which span and why”.

### Scope / Implementation Notes

- Define a small set of backend types (e.g., `ollama`, `gateway`, `azure`) and their required fields.
- Implement a loader (e.g., `load_for_repo(repo_root, env)`) that:
  - Reads repo-level defaults (TOML) and merges with environment.
  - Returns an ordered chain of backends with explicit priorities and labels.
- Refactor `qwen_enrich_batch.py` to:
  - Ask `enrichment_backends` for a backend choice per span or per batch.
  - Delegate health checking and host cycling to the module instead of hand-rolling it.

### Why Post-MVP

- The current hardening work (timeouts, health checks, logging) makes enrichment safe enough for day-to-day use.
- This module is where the real “magic” and future UX lives; it deserves its own design/SDD and should land once the core RAG service is stable.

---

## Post-MVP – Modular Enrichment Pipeline & Plugin Architecture

**Type:** Epic / Post-MVP  
**Theme:** RAG / Enrichment / Extensibility

### Problem / Why

Enrichment logic today is tightly coupled to the core RAG pipeline (e.g., `qwen_enrich_batch.py`). That works for a single “house style” of enrichment (summaries + a bit of schema) but does not scale to:

- Optional features (schema-enriched RAG, graph experiments, academic transforms).
- Different user profiles (simple “vanilla RAG” vs. “research lab” modes).
- Safe plugin-style experimentation over time.

We need a modular enrichment pipeline so LLMC can host multiple enrichment “modules” (summarization, schema, graph, etc.) without baking those behaviors into a single script.

### Goal

Create a pluggable enrichment pipeline with a small, stable contract:

- Core RAG code stays responsible for spans, storage, retrieval, and orchestration.
- Enrichment becomes an ordered list of steps (modules) that each transform spans.
- Each step can be turned on/off via config (per repo or globally).

In short:

> Codec is the engine; enrichment steps are bolt-on modules.

### Scope (In)

- Introduce an explicit enrichment pipeline layer (for example `tools/rag/enrichment_pipeline.py`).
- Define a minimal interface for an enrichment step, e.g.:

  ```python
  def run(spans, context) -> list[Span]:
      ...
  ```

- Implement at least one step using this pattern that mirrors the current baseline summarization.
- Add a pipeline config surface (likely `llmc.toml`):

  ```toml
  [enrichment.pipeline]
  steps = ["basic_summarization"]
  ```

- Make the main enrich script call something like:

  ```python
  pipeline.run_pipeline(spans, pipeline_config, backend_chain)
  ```

  instead of inlining all enrichment logic.
- Keep all existing behavior working if no pipeline config is present (default pipeline = current behavior).

### Scope (Out / Later)

- Full schema-enrichment pipeline (multi-pass graph / relations / cross-doc work).
- Complex routing (per-file, per-span, per-language).
- UI/CLI for managing pipelines.
- Multi-tenant plugin distribution/sharing.

This epic is about carving a clean seam, not filling it with every future feature.

### Functional Requirements

- **Pipeline execution**
  - Given spans and pipeline config, execute steps in order.
  - Pass the current span list (or context) through each step.
  - Return enriched spans to the caller.
- **Step registration**
  - Central registry mapping step names → callables (e.g. `"basic_summarization" -> basic_summarization.run`).
  - Unknown step name: either log-and-skip or fail fast with a clear message (to be decided in the SDD).
- **Config-driven behavior**
  - Pipeline configuration via `llmc.toml` under `[enrichment.pipeline]`.
  - If config is missing: use a baked-in default equal to “current behavior”.
- **Backwards compatibility**
  - Existing installs must still sync/enrich/generate context as today with no config changes.

### Non-Functional Requirements

- Low cognitive load: adding a step is “create module + register function + add name to config”.
- Minimal diffusion: new modules should not reach deep into unrelated subsystems.
- Testability: steps are testable in isolation with synthetic spans.

### Acceptance Criteria

- New module (e.g. `tools/rag/enrichment_pipeline.py`) with a core entrypoint such as:

  ```python
  run_pipeline(spans, pipeline_config, backend_chain, context)
  ```

- At least one existing enrichment path converted into a step (e.g. `basic_summarization.run(spans, context)`).
- Config surface in `llmc.toml` (or equivalent) supports `[enrichment.pipeline]` and a `steps` array.
- No config present → enrichment still works exactly as before for a default repo.
- Docs updated:
  - How to enable/disable enrichment modules via config.
  - How to add a custom enrichment step.
- Basic tests:
  - `run_pipeline` runs multiple steps in order.
  - Unknown step names are handled gracefully.
  - Default pipeline matches existing behavior.

---

## Post-MVP – RAG Hardening Tests & Operator Docs

The current RAG hardening work (timeouts, health checks, daemon logging, heartbeats) is implemented but not yet fully covered by tests or operator-facing documentation.

### Problem / Why

- There are no unit/integration tests that exercise:
  - `ENRICH_SUBPROCESS_TIMEOUT_SECONDS` behavior (timeout vs. success).
  - `ENRICH_HEALTHCHECK_ENABLED` behavior (healthy vs. unhealthy backends).
  - Heartbeat logging under long-running enrichment batches.
- Operators do not yet have a single place that documents:
  - How to diagnose a “hung” enrichment vs. a timed-out one.
  - How to interpret `~/.llmc/logs/rag-daemon/rag-service.log` and `logs/enrichment_metrics.jsonl`.
  - How to safely tweak timeouts, batch sizes, and health-check knobs.

### Goal

Raise the “operational readiness” of hardening features to match their implementation quality by:

- Adding targeted tests around the hardening paths.
- Writing a short, focused operator guide for RAG enrichment hardening.

### Scope (In)

- **Tests**
  - Add unit tests that:
    - Simulate a long-running child process and assert `run_enrich` raises after the configured timeout.
    - Exercise health check behavior with:
      - No reachable hosts.
      - Some reachable hosts.
      - Health check disabled via `ENRICH_HEALTHCHECK_ENABLED=off`.
    - Verify heartbeat logging is emitted for large batches (can be log-capture based).
  - Add a minimal integration-style test that:
    - Runs `qwen_enrich_batch.py` against a fake or stub backend.
    - Confirms metrics/log files are created at the expected paths.
- **Docs**
  - Add a short operator doc (e.g. `DOCS/RAG_Enrichment_Hardening.md`) that covers:
    - Environment knobs: `ENRICH_SUBPROCESS_TIMEOUT_SECONDS`, `ENRICH_HEALTHCHECK_ENABLED`, `ENRICH_MAX_SPANS`, `ENRICH_BATCH_SIZE`.
    - Where to find logs/metrics and what to look for.
    - Common failure modes: LLM down, timeouts, schema/validation errors.

### Scope (Out)

- Full-blown CI matrix for all possible backend combinations.
- Detailed dashboards or log shipping; this epic stops at “tests + operator docs”.

### Acceptance Criteria

- Tests exist and are runnable locally to verify:
  - Timeout behavior.
  - Health check behavior (enabled/disabled, reachable/unreachable).
  - Heartbeat logging for multi-span batches.
- A concise doc exists and is discoverable from the main README/roadmap that explains:
  - How to operate and tune the enrichment hardening features.
  - How to diagnose common issues.

---

## R&D – Experimental & Research Tasks

  1. Graph Enrichment & Intelligence (Phase 2/3 Follow-ups)                                                                                                                                                                                                                     
   * Fuzzy Linking: Match enrichment data to code spans using fuzzy logic (e.g., Levenshtein distance on function signatures) instead of just exact line numbers, making the graph robust to minor code edits.                                                                  
   * The "Gist" Layer: Auto-aggregate child summaries (e.g., summarize all methods in a class) to create synthesized "Class Summaries" or "Module Summaries" where none exist.                                                                                                  
   * Graph Pruning: Automatically prune graph nodes that have zero enrichment and zero meaningful connections to keep the context window small and potent.                                                                                                                      
   * Instructional Metadata: Instead of just "summaries", store specific "Intelligence Boosters" like:                                                                                                                                                                          
       * usage_guide: "Do X, don't do Y."                                                                                                                                                                                                                                       
       * related_concepts: "See also Auth Module."                                                                                                                                                                                                                              
       * pitfalls: "This function is not thread-safe."                                                                                                                                                                                                                          
   * Confidence Scoring: Color graph nodes by "how well we understand them" (Enriched vs. Raw vs. Stub) to help the agent decide which path to trust.                                                                                                                           
                                                                                                                                                                                                                                                                                
  2. Tooling & Agent UX                                                                                                                                                                                                                                                         
   * Semantic Hyperlinks: Use enrichment data to create links between disparate parts of the graph (e.g., if a comment mentions "Auth", link it to the Auth module even without an import).                                                                                     
   * "Adaptive Detail": Store multiple levels of enrichment (One-line gist vs. Full technical spec) and serve the right one based on the user's query intent.                                                                                                                   
   * Self-Correcting Tools: The "Tool Manifest" idea (P1) where invalid commands return a menu of valid commands to help the agent self-heal.                                                                                                                                   
                                                                                                                                                                                                                                                                                
  3. Testing & Quality                                                                                                                                                                                                                                                          
   * Mocking Strategy: Move away from subprocess.run for internal CLI testing. Use direct python calls with mocked args to avoid "environment flakiness" and timeouts.                                                                                                          
   * Hermeticity: Continue the "Ruthless" path of testing with read-only filesystems, locked databases, and missing binaries to bulletproof the agent.                                                                                                                          
                                                                                                                                                                                                                                                                                
  4. Research / Big Picture                                                                                                                                                                                                                                                     
   * "Vibrations" (Literature Graph): Apply this exact "Structure + Meaning" graph engine to creative writing (Entities = Characters, Calls = Interactions, Enrichment = Vibe/Theme).                                                                                           
   * Local LLM Optimization: The core thesis: Making "dumb" local models (Minimax/7B) perform like "smart" models (GPT-4) by feeding them this high-quality, pre-chewed graph context.         


### Vibrations HLD – Non-Code Fuzzy Fast Relationship Engine

**Type:** R&D / Research Task
**Theme:** Narrative Meaning Field Engine / AI-Assisted Authoring
**Source:** `/home/vmlinux/Downloads/LLMC_VIBRATIONS_HLD.md`
**Documentation:** `DOCS/RESEARCH/VIBRATIONS.md`

**Goal:**
Research and prototype a "vibrations" engine that builds a **narrative meaning field** over long-form text (novels, serial fiction, worldbuilding docs). The system maintains a scene + vibe graph capturing entities (characters, locations, objects), actions, and emotional tones/themes ("vibes") for fast, contextual recall while authoring.

**Research Focus:**
- **Fuzzy relationship extraction** using embeddings and LLM analysis
- **Fast ANN indexing** for realtime scene suggestions
- **LLM-based scene enrichment** for summaries, tone tags, and themes
- **Graph-based narrative memory** with SQLite backing
- **Live authoring integration** with sub-100ms reminder queries

This is a **research task**—the goal is exploration and proof-of-concept, not production hardening. See `DOCS/RESEARCH/VIBRATIONS.md` for full technical details and architecture.
