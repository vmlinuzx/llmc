# SDD — LLMC RAG Nav Task 4: Context Gateway & Freshness/Fallback Routing

## 1. Scope

Task 4 introduces a **Context Gateway** for LLMC RAG Nav that:

- Evaluates the freshness of the schema-enriched graph/index for a repo.
- Decides whether to route queries to the RAG graph or a local fallback.
- Ensures all tool results are tagged with a `freshness_state` and
  `source` label.

This sits on top of the metadata (Task 1), graph builder (Task 2),
and RAG-only tools (Task 3).

## 2. Responsibilities

- Provide a single function that, given a repo root, returns a routing
  decision (`RouteDecision`).
- Encapsulate freshness logic based on:
  - IndexStatus fields.
  - Current git HEAD SHA (if available).
- Wrap existing RAG-only tools so they:
  - Use the graph when it is known to be fresh.
  - Fall back to scanning the live repo when freshness is unknown or
    stale.
  - Tag results with:
    - `source`: `"RAG_GRAPH"` or `"LOCAL_FALLBACK"`
    - `freshness_state`: `"FRESH"`, `"STALE"`, or `"UNKNOWN"`.

## 3. Data Structures

New types in `tools.rag_nav.models`:

- `FreshnessState = Literal["FRESH", "STALE", "UNKNOWN"]`
- `SourceTag = Literal["RAG_GRAPH", "LOCAL_FALLBACK"]`

Result types now use these for:

- `SearchResult.source`, `SearchResult.freshness_state`
- `WhereUsedResult.source`, `WhereUsedResult.freshness_state`
- `LineageResult.source`, `LineageResult.freshness_state`

New dataclass in `tools.rag_nav.gateway`:

```python
@dataclass
class RouteDecision:
    use_rag: bool
    freshness_state: FreshnessState
    status: Optional[IndexStatus]
```

## 4. Freshness Policy

Implemented in `compute_route(repo_root: Path) -> RouteDecision`:

- Load `IndexStatus` via `load_status(repo_root)`.
- If there is **no status file**:
  - `use_rag = False`
  - `freshness_state = "UNKNOWN"`
- If `index_state != "fresh"`:
  - `use_rag = False`
  - `freshness_state = "STALE"`
- If `index_state == "fresh"`:
  - Determine git HEAD SHA for the repo with `git -C <repo> rev-parse HEAD`:
    - If HEAD or `last_indexed_commit` is missing:
      - `use_rag = False`
      - `freshness_state = "UNKNOWN"`
    - If HEAD == `last_indexed_commit`:
      - `use_rag = True`
      - `freshness_state = "FRESH"`
    - Otherwise:
      - `use_rag = False`
      - `freshness_state = "STALE"`

This is intentionally conservative: RAG is only used when we can
confidently assert freshness.

## 5. Tool Routing

The existing RAG-only tools in `tools.rag_nav.tool_handlers` are
updated to call `compute_route(repo_root)` and:

- If `use_rag` is True:
  - Load file list from `.llmc/rag_graph.json` via `_load_graph`.
  - Set `source = "RAG_GRAPH"`.
- If `use_rag` is False:
  - Derive file list via `_discover_source_files(repo_root)` (live walk).
  - Set `source = "LOCAL_FALLBACK"`.

All search logic (substring matching, snippet generation) remains
unchanged and is encapsulated in `_build_items_for_files`.

## 6. Affected APIs

Modified functions:

- `tool_rag_search(query, repo_root, limit=20) -> SearchResult`
- `tool_rag_where_used(symbol, repo_root, limit=50) -> WhereUsedResult`
- `tool_rag_lineage(symbol, direction, repo_root, max_results=50) -> LineageResult`

Each now:

- Resolves `repo_root`.
- Calls `compute_route(repo_root)` to obtain route + freshness.
- Chooses `files` from either the graph or the live repo.
- Returns results with updated `source` and `freshness_state` fields.

## 7. Testing Strategy

- `tests/test_rag_nav_gateway.py`:
  - `test_compute_route_no_status` → UNKNOWN, no RAG.
  - `test_compute_route_stale_status` → STALE, no RAG.
  - `test_compute_route_fresh_with_matching_head` (monkeypatched git)
    → FRESH, RAG.
  - `test_compute_route_fresh_with_mismatched_head` (monkeypatched git)
    → STALE, no RAG.

- `tests/test_rag_nav_tools.py` (updated):
  - Reuses the small two-file repo fixture and `build_graph_for_repo`.
  - Confirms that:
    - Search, where-used, and lineage return items.
    - `source` is either `"RAG_GRAPH"` or `"LOCAL_FALLBACK"`.
    - `freshness_state` is one of `"FRESH"`, `"STALE"`, `"UNKNOWN"`.

