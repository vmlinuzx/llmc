# SDD: Phase 3 - Public RAG Tools over DB + Graph

## 1. Introduction
This document specifies the implementation details for Phase 3 of the Graph Enrichment epic. The focus is on modifying the `tools.rag_nav` package to surface enrichment metadata (summaries, etc.) from the `rag_graph.json` artifact to the public API and CLI.

## 2. Data Structures

### 2.1 `tools.rag_nav.models`

We will update the item classes to support an `enrichment` field.

```python
@dataclass
class EnrichmentData:
    """Semantic enrichment for a code entity."""
    summary: Optional[str] = None
    usage_guide: Optional[str] = None
    # Extensible for future fields (inputs, outputs, etc.)
    
    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class SearchItem:
    file: str
    snippet: Snippet
    # ... existing fields ...
    enrichment: Optional[EnrichmentData] = None # New field

    def to_dict(self) -> dict:
        d = { ... } # existing
        if self.enrichment:
            d["enrichment"] = self.enrichment.to_dict()
        return d

# Apply similar updates to WhereUsedItem and LineageItem
```

## 3. Implementation Details

### 3.1 Graph Loading (`tools.rag_nav.tool_handlers`)

The existing `_load_graph` function reads `rag_graph.json`. We need to ensure it parses the `metadata` (or `enrichment`) field from the JSON nodes.

*   **Current JSON Node Structure** (from Phase 2):
    ```json
    {
      "id": "sym:auth.login",
      "path": "src/auth.py",
      "metadata": { "summary": "..." }
    }
    ```
*   **Proposed In-Memory Node Structure**: The `_load_graph` function currently returns a list of dicts. We just need to ensure it doesn't filter out `metadata`.
    *   *Verification*: Check `_load_graph` implementation. If it blindly `json.load`s, we might already have the data, and just need to access it.

### 3.2 Enrichment Attachment (`_maybe_attach_enrichment_*`)

In `tool_handlers.py`, there are existing helper functions like `_maybe_attach_enrichment_search`. Currently, these seem to try to hit the DB directly (a Phase 1 legacy/fallback path).

*   **Change**: We will modify `tool_rag_search` (and friends) to look up enrichment *from the loaded graph nodes first*.
*   **Logic**:
    1.  Load graph nodes: `nodes, edges = _load_graph(repo_root)`.
    2.  Index nodes by ID/Path for fast lookup.
    3.  For each result item (`SearchItem`):
        *   Find matching Graph Node.
        *   If Node has `metadata`, create `EnrichmentData` object.
        *   Assign to `item.enrichment`.

### 3.3 Tool Handlers

#### `tool_rag_search`
*   Existing flow: FTS Search -> List[SearchItem].
*   New flow:
    *   FTS Search -> List[SearchItem].
    *   `_attach_graph_enrichment(items, graph_nodes)`
    *   Return enriched list.

#### `tool_rag_where_used` & `tool_rag_lineage`
*   These tools *already* traverse the graph. They likely iterate over `nodes`.
*   We just need to update the loop where `WhereUsedItem` is created to pull `node.get("metadata")` and populate `item.enrichment`.

### 3.4 CLI Updates (`tools.rag_nav.cli`)

Update `_print_search`, `_print_where_used`, `_print_lineage` functions.

```python
def _print_search(res):
    # ... header ...
    for i, item in enumerate(res.items, 1):
        print(f"{i}. {item.file}")
        
        # NEW: Print enrichment
        if item.enrichment and item.enrichment.summary:
            print(f"   💡 Summary: {item.enrichment.summary}")
            
        # ... print snippet ...
```

## 4. Test Plan

### 4.1 Unit Test: `tests/test_rag_nav_enriched_tools.py` (New File)

We will create a new test file to verify Phase 3 specifically.

*   **`test_model_serialization`**: Create a `SearchItem` with `EnrichmentData`, call `to_dict`, assert structure.
*   **`test_tool_search_enrichment`**:
    *   Mock `_load_graph` to return nodes with metadata.
    *   Mock `fts_search` to return a hit matching a node.
    *   Call `tool_rag_search`.
    *   Assert result item has `enrichment` populated.
*   **`test_tool_where_used_enrichment`**:
    *   Mock graph with metadata.
    *   Call `tool_rag_where_used`.
    *   Assert result item has `enrichment`.

## 5. Tasks
1.  **Models**: Update `tools/rag_nav/models.py`.
2.  **Helpers**: Add `_attach_graph_enrichment` helper in `tool_handlers.py`.
3.  **Handlers**: Integrate helper into `tool_rag_search`.
4.  **Handlers**: Update `tool_rag_where_used` / `lineage` logic.
5.  **CLI**: Update `tools/rag_nav/cli.py` printing logic.
6.  **Tests**: Implement and run `tests/test_rag_nav_enriched_tools.py`.
