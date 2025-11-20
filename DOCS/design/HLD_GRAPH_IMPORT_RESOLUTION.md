# HLD: Graph Import Resolution Gap

**Date:** 2025-11-20  
**Status:** Draft  
**Author:** Ren (AI)  
**Related:** `tools/rag/graph.py`, `tools/rag/ast_checker.py`

## 1. Problem Statement
During the verification of `rag inspect`, we observed that `router.py` appeared as an "orphan" (0 incoming edges) in the graph, despite being explicitly imported and used by `qwen_enrich_batch.py`.

The current AST extraction logic fails to resolve imported symbols back to their source definitions. Instead, it treats calls to imported functions as calls to local symbols within the importing file.

**Example:**
- **Definition:** `scripts/router.py` defines `estimate_tokens_from_text`.
- **Usage:** `scripts/qwen_enrich_batch.py` does `from scripts.router import estimate_tokens_from_text` and calls `estimate_tokens_from_text()`.
- **Current Graph Edge:** `src:qwen_enrich_batch` -> `dst:sym:qwen_enrich_batch.estimate_tokens_from_text` (Non-existent local stub).
- **Desired Graph Edge:** `src:qwen_enrich_batch` -> `dst:sym:router.estimate_tokens_from_text`.

This fragmentation reduces RAG recall (missing "Used By" context) and causes false positives in isolation detection tools.

## 2. Root Cause Analysis
The Python AST extractor (`tools/rag/graph.py` or `schema.py` logic) likely follows a naive visitation strategy:

1.  **Import Phase:** It records `ImportFrom` nodes but likely does not persist a symbol table mapping local aliases to fully qualified names for the duration of the file visit.
2.  **Call Phase:** When visiting a `Call` node (e.g., `func()`), it resolves the name `func`. If it doesn't find a fully qualified resolution, it defaults to `{current_module}.{func}`.
3.  **Linkage:** The graph builder trusts these `dst` IDs. Since the "local stub" doesn't exist as a defined node, the edge points to a phantom entity, and the actual definition node remains orphan.

## 3. Proposed Solution

### 3.1 Approach A: The "Proper" AST Resolution (Recommended)
Modify the AST visitor class to maintain a `Scope` context.

1.  **Symbol Table:** Initialize a dictionary `import_map` when parsing a file.
2.  **Visit Import:**
    - On `from scripts.router import estimate_tokens_from_text`, add entry: `{"estimate_tokens_from_text": "scripts.router.estimate_tokens_from_text"}`.
    - On `import os`, add entry `{"os": "os"}`.
3.  **Visit Call:**
    - When encountering `Call(func=Name(id='estimate_tokens_from_text'))`:
    - Check `import_map`.
    - **If found:** Emit edge `dst:sym:scripts.router.estimate_tokens_from_text`.
    - **If not found:** Emit edge `dst:sym:{current_module}.estimate_tokens_from_text` (assume local definition).

### 3.2 Approach B: Post-Process Graph Stitching (Alternative)
If AST modification is too risky/complex immediately, a graph post-processing pass could attempt to heal edges.

1.  Iterate all edges where `dst` is a "phantom" (no corresponding node definition).
2.  Check the `src` file's imports (requires storing imports as node metadata).
3.  If `src` file imports the symbol name from another module, re-write the edge `dst`.

*Analysis:* Approach B is brittle and requires keeping imports in metadata. Approach A is cleaner and fixes the data at the source.

## 4. Implementation Plan (Approach A)

### 4.1 Phase 1: AST Visitor Update
- **Target:** `tools/rag/graph.py` (or wherever the `NodeVisitor` subclasses live).
- **Change:**
    - Add `self.imports = {}` to the visitor.
    - Implement/Update `visit_Import` and `visit_ImportFrom` to populate `self.imports`.
    - Update `visit_Call` to query `self.imports` before formatting the `dst` ID.

### 4.2 Phase 2: Rebuild & Verify
- Run `llmc-rag-nav` (or equivalent build script) to regenerate the graph.
- Verify `router.py` has incoming edges.

## 5. Test Strategy

### 5.1 Reproduction Case
Create two temporary files:
- `tests/repro/definer.py`: `def hello(): pass`
- `tests/repro/importer.py`: `from definer import hello; hello()`

### 5.2 Assertions
1.  **Before Fix:** Graph contains node `sym:definer.hello` with in-degree 0.
2.  **After Fix:** Graph contains node `sym:definer.hello` with in-degree 1 (from `importer.py`).

## 6. Risks
- **Ambiguity:** Python imports can be complex (`from . import x`, wildcard `*`). We will focus on explicit absolute/relative imports first.
- **Performance:** Minimal impact; map lookup is O(1).
