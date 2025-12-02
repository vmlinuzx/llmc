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

- Align current `enrichment_backends.py` with the intended “pipeline” shape:
  - Make the interface for a single backend and a chain explicit and well‑typed.
  - Capture per‑backend attempt statistics (already mostly there) in a stable struct.
- Decide whether you still want a dedicated `enrichment_pipeline` module:
  - If **yes**: create a thin pipeline module that orchestrates:
    - span selection → backend chain → DB writes.
  - If **no**: update roadmap/docs to bless the current layout as the supported design.

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

### 1.5 Database Maintenance (Auto-Vacuum)

**Goal:** Keep the RAG SQLite database size under control automatically.

- Implement a periodic `VACUUM` maintenance task in the enrichment loop:
  - Run frequency configurable via `llmc.toml` (e.g., `vacuum_interval_hours = 24`).
  - Ensure it only runs if the interval has passed to avoid performance hits.
  - Helps reclaim disk space from deleted vectors/enrichments (currently ~16% fragmentation).

### 1.6 System Friendliness (Idle Loop Throttling)

**Goal:** Prevent the daemon from burning CPU when there is no work to do.

- Audit the main `llmc-rag-service` loop and worker polls.
- Implement exponential backoff or smarter sleep cycles when the work queue is empty.
- Ensure the daemon is "quiet" (low CPU/IO) when the repo is static.

### 1.7 MCP Server Experience (CLI Wrapper)

**Goal:** Make `llmc_mcp.server` as friendly and manageable as the RAG service.

- Create a proper CLI wrapper (`llmc-mcp`) with standard commands:
  - `start` (daemonize), `stop`, `restart`, `status`, `logs`.
- Add an interactive mode or TUI status screen when run directly.
- Ensure it handles process management cleanly (pidfiles, signal handling) so users don't need `pkill`.

### 1.8 MCP Tool Expansion

**Goal:** Expose critical navigation and inspection tools through MCP.

- Add missing RAG navigation tools (P0):
  - `rag_where_used` - Find all usages of a symbol across the codebase.
  - `rag_lineage` - Traverse dependency lineage (upstream/downstream).
  - `inspect` - Fast file/symbol inspection with graph + enrichment context.
- Add observability tools (P1):
  - `rag_stats` - RAG index statistics and health metrics.
  - `rag_plan` - Heuristic retrieval planning for queries.
- Update code execution stubs to include new tools.

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

### 2.2 Refactor MCP bootstrap prompt

**Goal:** Clean up `server.py` by moving the large bootstrap prompt to a separate file.

- Move `BOOTSTRAP` constant from `llmc_mcp/server.py` to `llmc_mcp/prompts.py` (or similar).
- Ensure it remains easily editable but doesn't clutter the main server logic.

### 2.2 Polyglot RAG support

**Goal:** Make the schema graph and RAG story work across more than just Python.

- Extend `SchemaExtractor` to handle at least one non‑Python language end‑to‑end (JS/TS is a good first target):
  - Tree‑sitter integration for parsing.
  - Entity and relation mapping that matches the existing graph model.
  - Tests against a real non‑Python sample repo.
- Update docs to describe language support explicitly (Python: full, JS/TS: beta, others: TBD).

### 2.3 Normalized RAG scores

**Goal:** Make “score” fields meaningful to humans and simple scripts.

- Add a normalized score (0–100) alongside raw similarity scores.
- Ensure CLIs and TUIs prefer the normalized score in their displays.
- Add a short doc note explaining:
  - How normalization works.
  - That normalized scores are comparable across queries.



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

---

## 4. How to use this roadmap

- When you start a work session, pull one item from **Now** and ignore the rest.
- When something from **Now** is truly finished, move its bullet (or a summarized version) into `ROADMAP_COMPLETED.md`.
- Periodically re‑shape **Next** and **Later** based on what is actually exciting or urgent.

The goal is not to track every tiny task, but to keep a **small, accurate map** of where LLMC is going *from here*.