# SDD: Fuzzy AST Linking (Resilient RAG)

## 1. Introduction
This document specifies the implementation for "Fuzzy AST Linking," a mechanism to locate code symbols at query time even if the source file has changed since the last index. This enables "Resilient RAG" functionality.

## 2. Data Structures

### 2.1 Symbol Locator API (`tools.rag.locator`)

We need a stateless, efficient function to locate a symbol in a source string.

```python
@dataclass
class SymbolLocation:
    start_line: int
    end_line: int

def locate_symbol(source: str, symbol_id: str, lang: str = "python") -> Optional[SymbolLocation]:
    """
    Parses the source and returns the current location of the symbol.    
    Args:
        source: The file content.
        symbol_id: The fully qualified symbol ID (e.g., "sym:src.auth.Auth.login").
        lang: "python" (others future).
        
    Returns:
        SymbolLocation if found, None otherwise.
    """
    pass
```

## 3. Implementation Details

### 3.1 The Locator (`tools/rag/locator.py`)

*   **Parsing:** Use `ast` for Python.
*   **Traversal:**
    *   Split `symbol_id` into parts (module path, class/function hierarchy).
    *   Example: `sym:src.utils.Helper.do_work`
        *   Strip `sym:` prefix.
        *   If file path is known context, we just need the symbol part `Helper.do_work`.
    *   Walk the AST. Find `ClassDef(name='Helper')`. Inside that, find `FunctionDef(name='do_work')`.
    *   Return `lineno` and `end_lineno`.

### 3.2 Integration Hook (`tools/rag_nav/tool_handlers.py`)

We will modify `_attach_graph_enrichment` (or create a new `_rebind_locations` step before it).

**Current Flow:**
`tool_rag_search` -> `items` (with stale snippets) -> `_attach_graph_enrichment` -> returns items.

**New Flow:**
`tool_rag_search` -> `items` (stale) -> `_rebind_items(items)` -> `_attach_graph_enrichment` -> returns items.

```python
def _rebind_items(items: List[SearchItem], repo_root: Path) -> List[SearchItem]:
    for item in items:
        # Optimization: Only rebind if we suspect drift? 
        # Or just do it lazily if the snippet looks wrong?
        # For P1: Do it if file mtime > graph mtime. (Requires checking graph mtime).
        # Simpler P1: Just try to rebind everything? No, too slow.
        
        # Let's try purely file-based check.
        # We actually don't need to check timestamps if the "locator" is fast.
        # But for Search, we got the item FROM the file content (grep/FTS).
        # So the item lines are actually "fresh" (from grep/FTS) but the ENRICHMENT node is "stale".
        
        # Wait! 
        # If we grep/FTS, we have the *current* line number.
        # The Graph Node has the *old* line number.
        # We need to match Item(current_line) to Node(old_line).
        
        # This changes the matching logic in `_attach_graph_enrichment`.
        pass
```

**Correction to Strategy:**
We don't need to "re-parse to find the line" if `grep/FTS` already gave us the line.
We need to "re-parse to find the **SYMBOL ID**" of the line we found.

**Revised Flow:**
1.  `tool_rag_search` finds text at `line 15`.
2.  We want to know: "What symbol is at line 15?"
3.  We parse the file. We find `def login` covers lines 14-20.
4.  We generate ID: `sym:auth.login`.
5.  We look up `sym:auth.login` in the Graph.
6.  We find the node (even if the graph says it's at line 10).
7.  We attach enrichment.

This is **Reverse Symbol Resolution**.

### 3.3 `tools/rag/locator.py` (Revised)

```python
def identify_symbol_at_line(source: str, line: int) -> Optional[str]:
    """
    Returns the qualified symbol ID (e.g., "sym:auth.login") that encloses the given line.
    """
    # 1. Parse AST.
    # 2. Walk nodes.
    # 3. Find the smallest node (Function/Class) that contains `line`.
    # 4. Construct qualified name.
    pass
```

### 3.4 Update `tools/rag_nav/tool_handlers.py`

Modify `_attach_graph_enrichment`.

*   **Old Logic:** Match `item.file` and `item.line` to `node.file` and `node.line`. (Fails if lines drifted).
*   **New Logic:**
    1.  Group items by file.
    2.  For each file involved:
        *   Parse source once.
        *   For each item in that file:
            *   Call `identify_symbol_at_line(ast, item.start_line)`.
            *   Get ID (e.g., `sym:auth.login`).
            *   Lookup Node by ID (not line!).
            *   Attach Enrichment.

## 4. Test Plan

### 4.1 `tests/test_fuzzy_linking.py`

*   **`test_identify_symbol_simple`**:
    *   Source: `def foo():\n  pass`
    *   Line: 1 or 2.
    *   Result: `sym:module.foo`.
*   **`test_identify_symbol_nested`**:
    *   Source: `class A:\n  def b(self):\n    pass`
    *   Line: 3.
    *   Result: `sym:module.A.b`.
*   **`test_integration_drift`**:
    *   Mock Graph: `foo` at line 10.
    *   Real File: `foo` at line 20 (inserted 10 lines).
    *   Item: Search hit at line 20.
    *   Action: Resolve symbol at line 20 -> `foo` -> Lookup Graph `foo` -> Success.

## 5. Tasks
1.  Create `tools/rag/locator.py` with `identify_symbol_at_line`.
2.  Update `tools/rag_nav/tool_handlers.py` to use this for matching instead of line overlap.
3.  Implement tests.

```
