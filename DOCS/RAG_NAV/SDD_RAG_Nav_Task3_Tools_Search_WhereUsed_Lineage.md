# SDD — LLMC RAG Nav Task 3: RAG-only Search, Where-Used & Lineage

## 1. Scope

Task 3 adds **RAG-only helper functions** for:

- Search over code (`tool_rag_search`)
- Where-used queries (`tool_rag_where_used`)
- Lineage queries (`tool_rag_lineage`, placeholder)

These operate over the minimal graph artifact produced by Task 2
(`.llmc/rag_graph.json`) and do **not** yet include freshness/fallback
routing (that is Task 4's job).

## 2. Responsibilities

- Provide stable result shapes (`SearchResult`, `WhereUsedResult`,
  `LineageResult`) that can be exposed via CLI/MCP.
- Implement simple, line-based substring search using the file list
  from the graph artifact.
- Keep behaviour predictable and side-effect free (no writes).

## 3. Data Structures

New dataclasses in `tools.rag_nav.models`:

- `SearchItem` / `SearchResult`
- `WhereUsedItem` / `WhereUsedResult`
- `LineageItem` / `LineageResult`

All result types include:

- `items: list[...]`
- `truncated: bool`
- `source: Literal["RAG_GRAPH"]`
- `freshness_state: Literal["UNKNOWN"]`

This ensures that later, when the Context Gateway adds real freshness
handling and fallbacks, the public shape stays consistent.

## 4. Behaviour

### 4.1 Graph Loading

- `tools.rag_nav.tool_handlers._load_graph(repo_root)`
  - Reads `.llmc/rag_graph.json` as JSON.
  - Expects a `files` field with a list of relative paths.
  - Raises `FileNotFoundError` with a friendly message if the graph
    is missing (caller should run `build-graph` first).

### 4.2 Search Implementation

- `_iter_matches(repo_root, files, needle, max_results)`
  - Iterates over `files`, opens each file, and scans line-by-line.
  - Yields `(rel_path, line_number, line_text)` tuples for lines
    containing `needle` (simple substring match).
  - Stops after `max_results` matches.

- `_make_snippet(repo_root, rel_path, line_no)`
  - Builds a 5-line window around the matching line.
  - Returns a `Snippet` with `SnippetLocation` covering the window.

- `tool_rag_search(query, repo_root, limit=20) -> SearchResult`
  - Uses `_load_graph` → `_iter_matches` → `_make_snippet`.
  - Returns `SearchResult` with:
    - `query`
    - `items` (list of `SearchItem`)
    - `truncated` (`True` if matches hit `limit`)
    - `source="RAG_GRAPH"`
    - `freshness_state="UNKNOWN"`

### 4.3 Where-Used Implementation

- `tool_rag_where_used(symbol, repo_root, limit=50) -> WhereUsedResult`
  - Identical mechanics to `tool_rag_search`, but semantically
    positioned as “where-used” rather than “search”.
  - Returns `WhereUsedResult` tagged with `symbol`.

### 4.4 Lineage Implementation (Placeholder)

- `tool_rag_lineage(symbol, direction, repo_root, max_results=50)`
  - Currently uses the same substring search as where-used.
  - Normalizes `direction` to `"upstream"` or `"downstream"`.
  - Returns `LineageResult` with a flat `items` list for now.
  - Designed so a future task can swap in real multi-hop graph
    traversal without changing the public API.

## 5. CLI Extensions

`tools.rag_nav.cli` adds subcommands:

- `search`
  - `--repo/-r`, `--query/-q`, `--limit/-l`
  - Prints a JSON-serialized `SearchResult`.

- `where-used`
  - `--repo/-r`, `--symbol/-s`, `--limit/-l`
  - Prints a JSON-serialized `WhereUsedResult`.

- `lineage`
  - `--repo/-r`, `--symbol/-s`, `--direction/-d`, `--max-results/-m`
  - Prints a JSON-serialized `LineageResult`.

## 6. Testing Strategy

- `tests/test_rag_nav_tools.py`
  - `_setup_repo` creates a tiny repo with:
    - `module_a.py` defining `target_symbol`.
    - `module_b.py` importing and calling `target_symbol`.
  - Calls `build_graph_for_repo` to ensure `.llmc/` artifacts exist.
  - Tests:
    - `tool_rag_search` finds `target_symbol` and returns at least
      one `SearchItem`.
    - `tool_rag_where_used` finds at least one usage in `module_b.py`.
    - `tool_rag_lineage` returns at least one `LineageItem` and
      a normalized direction.

