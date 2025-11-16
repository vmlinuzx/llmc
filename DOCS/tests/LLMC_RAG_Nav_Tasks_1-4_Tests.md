# LLMC RAG Nav (Tasks 1–4) — Test Plan for Codex

This document describes **high-value tests** for the Schema-Enriched RAG Nav
subsystem as defined in the RAG Nav SDDs (Tasks 1–4). It assumes the presence of:

- `IndexStatus` metadata (`.llmc/rag_index_status.json`),
- A graph artifact (`.llmc/rag_graph.json`),
- RAG-only helper tools for search, where-used, and lineage,
- A routing layer that chooses between graph/RAG/local tools.

## 1. Task 1 — Index Status Metadata

- Basic save/load:
  - Saving an `IndexStatus` record and immediately loading it returns identical data.
- Missing file:
  - When the status file is absent, callers receive a clear “no status” result, not an exception.
- Corrupt file:
  - Corrupt JSON yields:
    - A logged warning,
    - A safe default value,
    - No crash in daemons or CLI tools that consult status.
- Multi-repo behavior:
  - With multiple repos, status for each is stored and retrieved independently.

## 2. Task 2 — Graph Builder CLI

- CLI ergonomics:
  - `llmc-rag-nav graph build` (or equivalent) shows helpful `--help` output and exits 0.
- Small repo:
  - Running the graph builder on a tiny demo repo produces a small, readable graph file with:
    - Nodes for each file or symbol,
    - Edges for obvious imports/calls.
- Idempotent rebuild:
  - Re-running the graph builder without changes overwrites the artifact atomically
    without growing it or creating duplicates.
- Failure handling:
  - When graph generation fails part-way through:
    - The old graph artifact remains untouched,
    - A clear error is emitted and logged.

## 3. Task 3 — RAG-only Search / Where-Used / Lineage

- Search results:
  - `tool_rag_search` returns:
    - Stable result shapes (`SearchResult`) matching the SDD,
    - Correct paths/line ranges for simple keyword queries.
- Where-used:
  - For a known symbol used in multiple places, `tool_rag_where_used` finds all known usages.
- Lineage placeholder:
  - If `tool_rag_lineage` is not fully implemented yet, the function:
    - Returns a documented placeholder,
    - Does not silently lie with fake data,
    - Logs its incomplete status.
- Error cases:
  - Requests for unknown symbols or out-of-range paths return explicit “no results”,
    not empty-but-successful responses that look like success.

## 4. Task 4 — Context Gateway & Routing

- Routing rules:
  - When both graph and plain RAG are available:
    - Graph-backed lookups are preferred for where-used/lineage-style queries.
    - Plain RAG search is used as a fallback when graph coverage is missing.
- Freshness:
  - If status metadata indicates a stale index, the router:
    - Either refuses to answer,
    - Or routes to a “slow but fresh” path (e.g., direct search or MCP).
- Degradation:
  - When the graph artifact is missing or corrupt:
    - Routing gracefully degrades to basic RAG search,
    - A warning is logged for operators/agents.

## 5. CLI / MCP Tool Surfaces (Where Applicable)

- CLI tools:
  - `llmc-rag-nav search`, `where-used`, and `lineage` subcommands:
    - Accept obvious flags like `--symbol`, `--file`, `--json`.
    - Print human-readable output by default and structured JSON when requested.
- MCP tools:
  - If exposed via MCP:
    - Tool manifests correctly describe input/output schemas.
    - Invalid inputs result in well-typed errors, not process crashes.

## 6. Cross-Component Consistency

- File/path consistency:
  - Paths reported in Nav results match:
    - Paths used in RAG search results,
    - Paths stored in the SQLite index and graph artifacts.
- ID consistency:
  - Stable IDs (if present) for spans/nodes remain consistent across:
    - RAG index,
    - Graph artifact,
    - Nav results.

## 7. End-to-End “Where-Used / Lineage” Scenarios

- Simple where-used:
  - Given a small demo module that imports and calls a function in another file:
    - Where-used for the function returns the caller site.
- Multi-hop lineage (if implemented):
  - Given a chain of calls across 3+ modules:
    - Lineage view shows at least a basic chain (call graph) for a given function.
- Failure reporting:
  - Any missing or inconsistent information (e.g., symbol exists in RAG but not in graph)
    is surfaced in a way that a Ruthless Testing Agent can flag as a bug.
