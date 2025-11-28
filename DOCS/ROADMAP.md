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

### 1.4 Clean public story and remove dead surfaces

**Goal:** Reduce confusion and maintenance by cutting old interfaces.

- Tighten the README and top‑level docs:
  - Clearly state the supported entrypoints:
    - `llmc-rag`, `llmc-rag-nav`, `llmc-rag-repo`, `llmc-rag-daemon/service`, `llmc-tui`.
  - Call out what LLMC does *not* try to be (no hosted SaaS, no magic auto‑refactor).

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
  - Heuristics like “public API functions”, “classes”, and “callers with many edges” score higher.
- Update `rag inspect` / `inspect_entity` to:
  - Return a compact, ranked subset for LLMs by default.
  - Expose the full symbol list only on explicit request.

### 3.3 Router & agentic routing v2

**Goal:** Turn the existing routing design into a supported surface again.

- Decide the future of the router:
  - Either wire a new `llmc-route` CLI that wraps the routing library and shows tier choices and rationale.
  - Or keep routing strictly internal to enrichment and Desktop Commander tool selection.
- Align router docs with reality:
  - Keep the “*removed for now*” note until there is a stable CLI or policy file.



---

## 4. How to use this roadmap

- When you start a work session, pull one item from **Now** and ignore the rest.
- When something from **Now** is truly finished, move its bullet (or a summarized version) into `ROADMAP_COMPLETED.md`.
- Periodically re‑shape **Next** and **Later** based on what is actually exciting or urgent.

The goal is not to track every tiny task, but to keep a **small, accurate map** of where LLMC is going *from here*.
