Patch P1 — Wire Thin Adapters (RAG Nav)

**Goal:** Eliminate `TypeError` in `tests/test_rag_nav_tools.py` by exposing
correctly shaped adapter functions in `tools.rag.__init__` that forward to
`tools.rag_nav.tool_handlers`.

## Changes
- Edited: `tools/rag/__init__.py` — add three thin adapters:
  - `tool_rag_search(query: str, repo_root: Path, limit: int = 10)`
  - `tool_rag_where_used(symbol: str, repo_root: Path, limit: int = 10)`
  - `tool_rag_lineage(symbol: str, direction: str, repo_root: Path, max_results: int = 50)`

Adapters import their implementation lazily from
`tools.rag_nav.tool_handlers` to avoid circular imports.

## Rationale
- Tests and external callers import the tools from `tools.rag`. Previous stubs
  had incompatible signatures and returned plain lists. This patch fixes the
  interface without introducing new business logic.

## How to Apply
This file is checked into the repo as documentation only; the actual code
changes are already present under `tools/rag/__init__.py`.

