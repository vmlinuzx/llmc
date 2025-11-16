# Implementation SDD — LLMC RAG Nav Task 4: Context Gateway & Routing

## 1. Modules and Functions

### 1.1 `tools.rag_nav.models`

- Adds:
  - `FreshnessState = Literal["FRESH", "STALE", "UNKNOWN"]`
  - `SourceTag = Literal["RAG_GRAPH", "LOCAL_FALLBACK"]`
- Updates result dataclasses (`SearchResult`, `WhereUsedResult`,
  `LineageResult`) to use these types for `source` and
  `freshness_state`.

### 1.2 `tools.rag_nav.gateway`

- `@dataclass RouteDecision`
  - `use_rag: bool`
  - `freshness_state: FreshnessState`
  - `status: Optional[IndexStatus]`

- `_detect_git_head(repo_root: Path) -> Optional[str]`
  - Runs `git -C <repo_root> rev-parse HEAD`.
  - Returns SHA string or `None` on error.

- `compute_route(repo_root: Path) -> RouteDecision`
  - Implements the policy described in the main SDD:
    - No status → UNKNOWN, no RAG.
    - Non-fresh status → STALE, no RAG.
    - Fresh status + missing git info → UNKNOWN, no RAG.
    - Fresh status + matching HEAD → FRESH, RAG.
    - Fresh status + mismatched HEAD → STALE, no RAG.

### 1.3 `tools.rag_nav.tool_handlers`

- Adds helper:
  - `_build_items_for_files(...)`
    - Wraps `_iter_matches` + `_make_snippet` and produces a list
      of `SearchItem` / `WhereUsedItem` / `LineageItem` plus a
      `truncated` flag.

- Modifies:
  - `tool_rag_search`
  - `tool_rag_where_used`
  - `tool_rag_lineage`

  Each:

  - Resolves `repo_root`.
  - Calls `compute_route(repo_root)`.
  - Chooses `files` from either the graph (`_load_graph`) or live
    repo (`_discover_source_files`).
  - Constructs items using `_build_items_for_files` and the
    appropriate item constructor.
  - Returns a result with:
    - `source` set to `"RAG_GRAPH"` or `"LOCAL_FALLBACK"`.
    - `freshness_state` set to the route's freshness state.

### 1.4 `tools.rag_nav.cli`

- No behavioural changes beyond the underlying routing; CLI still
  exposes:
  - `build-graph`
  - `status`
  - `search`
  - `where-used`
  - `lineage`

## 2. Error Handling

- The gateway is deliberately conservative:
  - Any ambiguity (missing status or git data) defaults to not using
    the RAG graph.
- Missing graph file when `use_rag=True` still results in a
  `FileNotFoundError` raised by `_load_graph`; callers (e.g. CLI)
  will see a traceback in this version. A future refinement could
  catch this and fall back automatically.

## 3. Integration Notes

- Task 4 does not change the on-disk format of:
  - `.llmc/rag_index_status.json`
  - `.llmc/rag_graph.json`
- It only affects **how** those artifacts are used at query time.
- This means Tasks 1–3 remain compatible; existing builds and
  indices continue to work under the new routing policy.

## 4. Testing

- `tests/test_rag_nav_gateway.py` ensures routing logic behaves as
  expected under different IndexStatus + git scenarios, using
  pytest's `monkeypatch` to control `_detect_git_head`.

- `tests/test_rag_nav_tools.py` now asserts only that `source` is
  one of the two allowed tags and that `freshness_state` is one of
  the three allowed values. In a non-git tmp repo, these will
  typically be:
  - `source = "LOCAL_FALLBACK"`
  - `freshness_state = "UNKNOWN"`

