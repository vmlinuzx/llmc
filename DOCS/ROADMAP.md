# LLMC Roadmap

This roadmap consolidates the previous `ROADMAP.md`, `Roadmap.md`, and `ROADMAP_P1_Tool_Contract_Self_Describing_Tools.md` into a single, canonical document for this repo.

---

## Phases

- **P0 – Immediate**: critical bugs, auth, deploy blockers.
- **P1 – Core**: main feature set, happy-path flows.
- **P2 – Quality**: performance, DX polish, observability, docs.
- **P3 – Nice-to-have**: experiments, stretch goals.

---

## Current Priorities

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

---

## Backlog (Condensed)

This section is a trimmed, de-duplicated version of the prior backlog; items remain small (1–3 days) and implementation details live in the code/docs they reference.

### RAG & Context Quality

- Complete schema-enriched/graph-style RAG integration and validation benchmarks.
- Standardize RAG architecture across wrappers using a shared helper (e.g., `scripts/rag_common.sh`).
- Harden freshness automation (cron-friendly refresh wrapper + docs/locks/logs).
- Introduce AST-driven chunking for key languages (Python, TS/JS, Bash, Markdown).

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

