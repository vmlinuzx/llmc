# Audit Charter: Context Navigation (Graph & Symbols)

**Target Systems:**
*   `llmc/rag_nav/` (Graph logic, tools)
*   `llmc/mcread.py` (File reading & graph context attachment)
*   `llmc/mcinspect.py` (Symbol resolution)

**The Objective:**
Ensure that "Navigating" the code is instant. Users hate latency. If `mcinspect` takes 3 seconds, the user has already context-switched to Reddit.

**Specific Hunting Grounds:**

1.  **The Graph Rebuilder:**
    *   `llmc/rag_nav/tool_handlers.py`.
    *   We know it rebuilds the graph often. Find *every* trigger.
    *   Does `load_graph` parse the JSON every single time a tool is called? (Hint: It probably does. Fix it.)

2.  **The Symbol Resolution Hunt:**
    *   `llmc/symbol_resolver.py`.
    *   How does it find "MyClass"? Does it grep? Does it use the graph?
    *   If it uses `grep` first, why do we have a graph? If it uses the graph, why is it slow?

3.  **The Context Explosion:**
    *   `llmc/mcread.py`.
    *   When we read a file, we "attach context." How much?
    *   Are we accidentally loading the entire dependency tree?
    *   Check for "Recursive Import Loading" where reading file A loads B, which loads C... until OOM.

4.  **The JSON Parse Tax:**
    *   The graph is stored in `.llmc/rag_graph.json`.
    *   If this file is 50MB, parsing it takes time.
    *   Are we using a streaming parser? Or `json.load()`?
    *   Why aren't we using SQLite for the graph nodes yet?

**Command for Jules:**
`audit_nav --persona=architect --target=llmc/rag_nav`
