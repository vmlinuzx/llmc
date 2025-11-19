# Desktop Commander Tool Manifest

**Authoritative Source for LLMC RAG Navigation Tools**

This manifest defines the tools available for Desktop Commander (and other MCP clients) to interact with the LLMC RAG system. Agents should use these tools for code exploration and understanding.

## 1. `llmc-rag-nav search`

*   **Description**: Search the codebase for a string or regex pattern. Uses RAG enrichment (summaries, usage guides) when available.
*   **Parameters**:
    *   `repo` (string, required): Path to the repository root.
    *   `query` (string, required): The search string or regex.
    *   `limit` (integer, optional): Maximum number of results (default: 20).
*   **Returns**: `RagResult` (JSON envelope) containing `SearchItem` list.
*   **Side Effects**: Read-only.
*   **Danger Level**: Low.

## 2. `llmc-rag-nav where-used`

*   **Description**: Find all usages of a specific code symbol (function, class, variable). Uses graph index for high precision.
*   **Parameters**:
    *   `repo` (string, required): Path to the repository root.
    *   `symbol` (string, required): The name of the symbol to find (e.g., `login`, `Auth`).
    *   `limit` (integer, optional): Maximum number of results (default: 50).
*   **Returns**: `RagResult` containing `WhereUsedItem` list.
*   **Side Effects**: Read-only.
*   **Danger Level**: Low.

## 3. `llmc-rag-nav lineage`

*   **Description**: Analyze the call graph lineage (callers or callees) of a symbol.
*   **Parameters**:
    *   `repo` (string, required): Path to the repository root.
    *   `symbol` (string, required): The name of the symbol.
    *   `direction` (string, optional): "upstream" (callers) or "downstream" (callees). Default: "downstream".
    *   `limit` (integer, optional): Maximum number of results (default: 50).
*   **Returns**: `RagResult` containing `LineageItem` list.
*   **Side Effects**: Read-only.
*   **Danger Level**: Low.

## 4. `llmc-rag-nav status`

*   **Description**: Check the health and freshness of the RAG index.
*   **Parameters**:
    *   `repo` (string, required): Path to the repository root.
*   **Returns**: JSON with `index_state`, `last_indexed_at`, `last_indexed_commit`.
*   **Side Effects**: Read-only.
*   **Danger Level**: Low.

## 5. `llmc-rag-nav build-graph`

*   **Description**: Rebuild the RAG graph and index for the repository. Use this if the status is STALE.
*   **Parameters**:
    *   `repo` (string, required): Path to the repository root.
*   **Returns**: Text/JSON confirmation.
*   **Side Effects**: Writes to `.llmc/` directory (DB, JSON). High CPU usage.
*   **Danger Level**: Medium (Resource intensive).
