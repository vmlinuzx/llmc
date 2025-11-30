# LLMC Routing & Enrichment Epic – High-Level SDD (1‑Pager)

## 1. Purpose

This document gives a **high-level map of the LLMC routing & enrichment epic** so a new context/agent can quickly understand:
- What we’re doing,
- How work is phased,
- Which phase is currently in focus.

It is not a deep SDD; it’s a **navigation card** that points to the detailed SDDs per phase.

---

## 2. Scope

Applies to the LLMC subsystems involved in:

- **Content classification & metadata** (slice_type, content_type, language).
- **Embedding routing** (docs vs code vs ERP, single-/multi-route).
- **Query routing** (deterministic and configurable).
- **Enrichment routing** (content-type–aware enrichment chains).
- **Evaluation & guardrails** (routing eval, enrichment eval, metrics).

Out of scope:
- Core RAG engine internals not touched by routing.
- Non-RAG agents, tools, or day-job–specific workflows.

---

## 3. Phase Overview

Each phase has:
- A **design doc / SDD** (already written or to-be-written).
- A **code implementation phase** (patch + tests).
- Optional **eval/hardening** work.

You can start any session by saying:  
> “We are working on **Phase N: <name>** of the LLMC routing & enrichment epic.”

### Phase 1 – Foundations (Schema & Classification)

**Goal:**  
Introduce deterministic slice classification and the metadata needed for routing.

**Key outcomes:**
- New slice/enrichment/embedding columns:
  - `slice_type`, `slice_language`, `classifier_confidence`, `classifier_version`
  - `route_name`, `profile_name`
  - `content_type`, `content_language`, etc.
- Deterministic `classify_slice(...)` based on:
  - File extension, shebang, simple syntax hints.
- No behavior change to retrieval yet (still docs-only).

---

### Phase 2 – Code Route & Jina Integration (Ingest Only)

**Goal:**  
Split embeddings into **docs** and **code**, using Jina Code for code slices.

**Key outcomes:**
- Embedding profiles:
  - `default_docs` → `emb_docs`
  - `code_jina` (jina-embeddings-v2-base-code) → `emb_code`
- Routing:
  - `slice_type="code"` → route `code` → `code_jina` / `emb_code`
  - Other types → route `docs` → `default_docs` / `emb_docs`
- Queries still go through docs route only.

---

### Phase 3 – Query Routing (Deterministic)

**Goal:**  
Route queries to **docs vs code** deterministically.

**Key outcomes:**
- `classify_query(text, tool_context)` → `route_name` (`docs` or `code`) + `confidence` + `reasons`.
- Config flag: `routing.options.enable_query_routing`:
  - `false` → legacy docs-only behavior.
  - `true` → use `classify_query` to pick `docs` or `code`.
- Safe fallbacks: misconfig → log + fall back to docs.

---

### Phase 4 – Enrichment Tagging & Prompt Annotations

**Goal:**  
Ensure enrichment records and prompts are **type-aware**.

**Key outcomes:**
- Enrichment rows mirror slice metadata:
  - `content_type`, `content_language`, `content_type_confidence`, `content_type_source`.
- Enrichment prompts prepend headers like:
  - `[CONTENT_TYPE: code]`, `[LANGUAGE: python]`
- RAG prompts annotate chunks:
  - `[TYPE: docs]`, `[TYPE: code, LANG: python]`, etc.

---

### Phase 5 – Hardening, Config Polish & Metrics

**Goal:**  
Make routing **robust, debuggable, and observable**.

**Key outcomes:**
- Safe defaults for:
  - Unknown `slice_type` → route `docs`.
  - Missing routes/profiles → clear errors or fallback to docs.
- Central helpers:
  - `get_route_for_slice_type(...)`
  - `resolve_route(route_name)`.
- Metrics:
  - Counts of slices/queries per route.
  - Fallback counters.
- Routing docs (`ROUTING.md`) describing config knobs & behavior.

---

### Phase 6 – Multi-Route Retrieval & Score Fusion

**Goal:**  
Optionally retrieve from **multiple routes** (e.g. code + docs) and fuse scores.

**Key outcomes:**
- Config:
  - `routing.options.enable_multi_route`
  - `routing.multi_route.code_primary`, `routing.multi_route.docs_primary`
- Retrieval pipeline:
  - Primary route + optional secondary routes (each with a weight).
  - Per-route normalization + weighted score fusion.
- Fully backwards compatible when disabled.

---

### Phase 7 – ERP/Product Route & Index

**Goal:**  
Add a dedicated **ERP/product route** using its own index.

**Key outcomes:**
- New route: `erp` → `emb_erp` (uses docs embedder initially).
- Slice classification:
  - `slice_type="erp_product"` for ERP/PIM/product slices.
- Query routing:
  - ERP-style queries (SKUs, model numbers, Amazon/ERP issues) → route `erp`.
- Optional participation in multi-route retrieval.

---

### Phase 8 – Router Abstraction & Routing Eval Harness

**Goal:**  
Make routing **pluggable** and **measurable**.

**Key outcomes:**
- `Router` abstraction:
  - `Router.decide_route(query_text, tool_context) -> {route_name, confidence, reasons}`
  - `DeterministicRouter` as the default implementation.
  - Config: `routing.options.router_mode = "deterministic"`.
- Routing eval CLI:
  - JSONL dataset with `query`, `expected_route`, `relevant_slice_ids`.
  - Metrics: routing accuracy, hit@k, MRR.

---

### Phase 9 – Enrichment Chains & Enrichment Eval

**Goal:**  
Make enrichment **content-type–aware and testable**.

**Key outcomes:**
- Content-type–aware enrichment chains:
  - `enrichment.profiles.*`
  - `enrichment.chains.docs_basic`, `code_basic`, `erp_basic`, etc.
  - Mapping: `enrichment.routing.content_type_to_chain`.
- Chain runner:
  - Executes ordered steps with per-step prompts & profiles.
- Enrichment eval & guardrails harness:
  - JSONL slice dataset with expected keys per content type.
  - CLI: `llmc enrich eval --dataset ... --chain_overrides ...`
  - Structural validation (summary present, functions extracted, attributes normalized).

---

## 4. How to Use This Document

When starting a new context or handing work to an agent/model:

1. Provide this 1-pager.
2. Provide the **detailed SDD** for the phase you’re targeting (e.g. Phase 3, 5, or 9).
3. Say explicitly:
   > “We are currently implementing **Phase X – <name>**.  
   > Assume previous phases are designed as above and either implemented or in progress.”

This keeps each session focused on the **current phase**, while preserving the larger roadmap in a compact form.
