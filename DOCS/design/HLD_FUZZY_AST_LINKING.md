# HLD: Fuzzy AST Linking (Resilient RAG)

## 1. Goal
To make the LLMC RAG system resilient to code edits by decoupling enrichment retrieval from unstable line numbers. The system should use **AST Anchors** (Qualified Symbol Names) to locate code entities at runtime, allowing enriched context to be served even if the file has changed since the last index.

## 2. Problem Statement
*   **Brittle Linking:** Currently, `rag_graph.json` stores static line numbers (e.g., `start_line: 10`).
*   **Drift:** If a developer inserts 5 lines at the top of `auth.py`, the function `login()` moves to line 15.
*   **Failure:** The RAG tool either returns the wrong text (lines 10-20, which is now garbage) or the "Freshness Gate" blocks the request entirely because the file hash changed.
*   **Impact:** Users lose RAG intelligence exactly when they need it most—while editing code.

## 3. Proposed Solution: Runtime AST Re-binding
Instead of trusting the static line numbers in the graph, we treats them as "hints." At runtime, if the file has changed, we re-parse it to find the *current* location of the entities.

### 3.1 Core Concept: The Anchor
*   **Anchor ID:** A stable identifier derived from the code structure.
    *   Python: `module.class.method` (e.g., `src.auth.Auth.login`).
*   **Process:**
    1.  **Index Time:** Store `id="sym:src.auth.Auth.login"` and `hint_lines=10-20`.
    2.  **Query Time:**
        *   Check file freshness.
        *   If fresh -> use `hint_lines`.
        *   If stale -> **Re-bind**.
    3.  **Re-bind:**
        *   Parse `src/auth.py` into AST.
        *   Find node `Auth` -> `login`.
        *   Update in-memory node with *new* lines (e.g., 15-25).
        *   Serve result using new lines + old enrichment.

## 4. Key Components

### 4.1 `tools.rag.schema` (Schema Updates)
*   Ensure `Entity.id` is rigorously standardized as the stable anchor.
*   No schema changes required if `id` is already unique and structural (it appears to be `sym:{module}.{name}`).

### 4.2 `tools.rag.locator` (New Module)
*   A lightweight, AST-based symbol locator.
*   **Input:** File source code, target Symbol ID.
*   **Output:** `SnippetLocation` (start_line, end_line) or `None`.
*   **Performance:** Must be sub-10ms per file. Use `ast` module (Python) or regex heuristics (other langs).

### 4.3 `tools.rag_nav.tool_handlers` (Integration)
*   Modify `tool_rag_search` and `tool_rag_where_used`.
*   **Logic Hook:**
    ```python
    if file_is_dirty(path):
        new_loc = locator.find_symbol(path, entity_id)
        if new_loc:
            entity.start_line = new_loc.start_line
            entity.end_line = new_loc.end_line
    ```

## 5. Data Flow
1.  **User Query:** `where-used login`
2.  **Graph Lookup:** Finds `Entity(id="sym:auth.login", path="auth.py", lines=10-20)`.
3.  **Freshness Check:** `auth.py` on disk != `auth.py` in index.
4.  **Re-bind Triggered:**
    *   Load `auth.py` from disk.
    *   Parse AST.
    *   Find `def login` inside `class Auth`.
    *   Result: `lines=15-25`.
5.  **Update:** In-memory Entity updated to `lines=15-25`.
6.  **Serve:** Result item created with lines 15-25 and original enrichment.

## 6. Test Strategy
*   **Unit Test (`test_locator.py`):**
    *   Input: A Python file content and a symbol path.
    *   Action: Parse and return location.
    *   Case: Symbol moved (lines shifted).
    *   Case: Symbol deleted (return None).
    *   Case: Symbol renamed (return None - link broken, acceptable).
*   **Integration Test:**
    *   Create a graph pointing to line 10.
    *   Modify the file on disk so the function is at line 20.
    *   Run `tool_rag_search`.
    *   Assert the returned snippet matches the *new* code at line 20, but still has the *old* enrichment.

## 7. Constraints / Risks
*   **Parsing Cost:** Parsing every dirty file on every query could be slow.
    *   *Mitigation:* Only parse files involved in the result set.
*   **Ambiguity:** Overloaded function names in languages without strict namespacing.
    *   *Mitigation:* Python's AST is precise. For others, fallback to "best effort."

## 8. Development Tasks
1.  **Create `tools/rag/locator.py`**: Implement `find_symbol_in_source(source, symbol_path)`.
2.  **Update `tool_handlers.py`**: Inject the re-binding logic before returning results.
3.  **Tests**: Add `tests/test_fuzzy_linking.py`.
