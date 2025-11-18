Patch P2 — Typed No‑Op Handlers (RAG Nav)

**Goal:** Implement signature‑correct handlers that return valid empty envelopes
from `tools.rag_nav.models`. This advances tests beyond early
import/signature failures while keeping logic minimal.

## Files
- `tools/rag_nav/tool_handlers.py`

## Handlers
- `tool_rag_search(query: str, repo_root, limit: int | None = None) -> SearchResult`
- `tool_rag_where_used(symbol: str, repo_root, limit: int | None = None) -> WhereUsedResult`
- `tool_rag_lineage(symbol: str, direction: str, repo_root, max_results: int | None = None) -> LineageResult`

## Notes
- These implementations intentionally return empty `items` lists; later patches
  will populate them using `.llmc/rag_graph.json` and local fallbacks.

