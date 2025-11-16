# Implementation SDD — LLMC RAG Nav Task 3: RAG-only Tools

## 1. Modules and Functions

### 1.1 `tools.rag_nav.models`

- Adds result dataclasses:
  - `SearchItem`, `SearchResult`
  - `WhereUsedItem`, `WhereUsedResult`
  - `LineageItem`, `LineageResult`
- All result types:
  - Reference `Snippet` / `SnippetLocation`.
  - Include `truncated: bool`.
  - Include `source: Literal["RAG_GRAPH"]`.
  - Include `freshness_state: Literal["UNKNOWN"]`.

### 1.2 `tools.rag_nav.tool_handlers`

New helpers:

- `_load_graph(repo_root: Path) -> dict`
  - Reads `.llmc/rag_graph.json`.
  - Raises `FileNotFoundError` with guidance if missing.

- `_iter_matches(repo_root, files, needle, max_results)`
  - Performs naive substring search.
  - Returns a list of `(rel_path, line_number, line_text)` tuples.

- `_make_snippet(repo_root, rel_path, line_no) -> Snippet`
  - Reads the file and slices a small window for context.

New public functions:

- `tool_rag_search(query, repo_root, limit=20) -> SearchResult`
  - Uses `_load_graph` and search helpers.
  - Populates `SearchResult` and returns it.

- `tool_rag_where_used(symbol, repo_root, limit=50) -> WhereUsedResult`
  - Same mechanics as search, but parameter/field names reflect
    “where-used” semantics.

- `tool_rag_lineage(symbol, direction, repo_root, max_results=50)`
  - Same search mechanics, but returns a `LineageResult` with:
    - `symbol`
    - `direction` normalized to `"upstream"` or `"downstream"`
    - `items` from matches.

### 1.3 `tools.rag_nav.cli`

- Extends existing CLI with:
  - `search`
  - `where-used`
  - `lineage`
- Each subcommand:
  - Resolves `--repo` to an absolute path.
  - Invokes the corresponding tool handler.
  - Prints JSON using `json.dumps(..., default=lambda o: o.__dict__)`.

## 2. Error Handling

- Missing graph file:
  - `_load_graph` raises `FileNotFoundError` with a message instructing
    the user to run `build-graph` first.
  - CLI will surface this as a traceback in the current task; a
    future refinement can catch and print a friendlier message.
- IO errors when reading individual files:
  - `_iter_matches` skips files that cannot be read.
  - `_make_snippet` falls back to a snippet with empty text if the
    file cannot be read.

## 3. Future Evolution

- The naive substring search can be replaced with:
  - AST-based symbol resolution.
  - Graph-based dependency traversal.
  - Language-agnostic token search.
- Because result types are already structured and include `source`/
  `freshness_state`, the Context Gateway (Task 4) can later wrap
  these and add fallback semantics without changing callers.

## 4. Testing

`tests/test_rag_nav_tools.py` verifies:

- `tool_rag_search` returns a `SearchResult` with non-empty `items`
  for a symbol that exists in `module_a.py`.
- `tool_rag_where_used` returns `WhereUsedResult` with at least one
  item referencing `module_b.py`.
- `tool_rag_lineage` returns `LineageResult` with non-empty `items`
  and a normalized direction.

