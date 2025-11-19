# HLD: Phase 3 - Public RAG Tools over DB + Graph

## 1. Goal
To surface the rich semantic metadata (enrichment) stored in the `SchemaGraph` to the public RAG tools (`search`, `where-used`, `lineage`). This ensures that when an agent or user queries the codebase, they receive not just code locations, but also high-level summaries, usage guides, and caveats, enabling "smarter" reasoning.

## 2. Problem Statement
*   **Phase 2 Success:** The `rag_graph.json` now contains enriched `Entity` nodes with metadata (summary, usage_guide).
*   **Current Gap:** The public tool handlers (`tool_rag_search`, `tool_rag_where_used`, `tool_rag_lineage`) currently return lightweight result objects (`SearchItem`, etc.) that only contain file paths and text snippets. They essentially "throw away" the enrichment data present in the graph.
*   **Consequence:** Downstream agents (like Minimax) have to read the raw code to understand it, defeating the purpose of the pre-computed enrichment.

## 3. Proposed Solution
We will upgrade the tool handlers to:
1.  **Load the Graph:** Efficiently load the enriched `SchemaGraph` (or a lookup index derived from it).
2.  **Match & Merge:** When a search result or graph traversal finds a node, retrieve its corresponding enrichment metadata.
3.  **Rich Return Types:** Return updated model objects (`SearchItem`, `WhereUsedItem`) that include an `enrichment` field.
4.  **CLI Display:** Update the CLI to display this enrichment (e.g., summaries) to the user.

## 4. Key Components

### 4.1 Data Models (`tools.rag_nav.models`)
*   Update `SearchItem`, `WhereUsedItem`, `LineageItem` to include an optional `enrichment: Dict[str, Any]` field.
*   Define a standardized `EnrichmentData` structure (or just use `Dict`) to ensure consistency (summary, usage_guide, etc.).

### 4.2 Tool Handlers (`tools.rag_nav.tool_handlers`)
*   **Graph Loading:** Ensure the full `SchemaGraph` (or an optimized index of it) is accessible to the tools. Currently, `_load_graph` loads a lightweight dict representation. We need to ensure this representation includes the `metadata` field from the `Entity` nodes.
*   **`tool_rag_search`**: After getting hits (from FTS/Reranker), lookup the corresponding graph node by file/symbol and attach enrichment.
*   **`tool_rag_where_used` / `tool_rag_lineage`**: Since these already traverse the graph, they just need to preserve the metadata from the visited nodes into the result items.

### 4.3 CLI (`tools.rag_nav.cli`)
*   Update the print formatters (`_print_search`, etc.) to check for `item.enrichment`.
*   If present, print the `summary` in a distinct color or format (e.g., indented, italicized) below the code location.

## 5. Data Flow
1.  **User/Agent** invokes `llmc-rag-nav search "auth"`.
2.  **Tool Handler** runs FTS search -> gets `src/auth.py:login`.
3.  **Lookup:** Handler checks the loaded Graph for the entity at `src/auth.py:login`.
4.  **Hit:** Graph node found. It has `metadata: { "summary": "Authenticates user...", "usage_guide": "..." }`.
5.  **Attach:** Handler creates `SearchItem` with `enrichment=metadata`.
6.  **Return:** `SearchResult` returned.
7.  **CLI:** Prints:
    ```
    1. src/auth.py:login
       Summary: Authenticates user via JWT.
       Code: def login(user)...
    ```

## 6. Test Strategy
*   **Unit Tests:**
    *   **Model Serialization:** Verify `SearchItem` with enrichment serializes to JSON correctly.
    *   **Graph Loading:** Verify `_load_graph` correctly parses the `metadata` field from `rag_graph.json` into the in-memory node dicts.
*   **Integration Tests (Mocked Graph):**
    *   Create a temporary `rag_graph.json` with enriched nodes.
    *   Call `tool_rag_where_used` for a known node.
    *   Assert the returned `WhereUsedResult` contains the enrichment data.
*   **CLI Smoke Test:** Run the CLI against the temp repo and assert the output string contains the summary text.

## 7. Constraints
*   **Performance:** Loading the full graph metadata into memory is acceptable for typical repo sizes (tens of thousands of nodes). For massive repos, we might need lazy loading, but for now, eager loading matches existing architecture.
*   **Output Size:** Enriched results are larger. We might need a flag to suppress details (e.g., `--concise`) if the agent just wants paths, but default should be "smart".

## 8. Development Tasks
1.  **Update Models:** Add `enrichment` field to `tools.rag_nav.models`.
2.  **Update Graph Loader:** Ensure `tools.rag_nav.tool_handlers._load_graph` preserves node metadata.
3.  **Update Handlers:** Modify `tool_rag_search`, `where_used`, `lineage` to attach metadata.
4.  **Update CLI:** Improve output formatting.
5.  **Tests:** Add `tests/test_rag_nav_enriched_tools.py`.