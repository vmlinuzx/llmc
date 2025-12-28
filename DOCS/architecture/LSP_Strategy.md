# LLMC Architecture: The "Mechanical Context" Strategy (LSP)

**Date:** 2025-12-28
**Status:** Implemented / Production

## 1. The Core Philosophy: "Stop Gaslighting the AI"

In traditional RAG (Retrieval-Augmented Generation), we treat the LLM like a stranger in a dark room. We force it to use tools like `list_dir` and `search_text` to stumble around the codebase, discovering files one by one. This is slow, error-prone, and wasteful ("Progressive Disclosure").

**The Pivot:** Instead of hiding the codebase, we give the Agent **Instant Omniscience**.

We achieve this by adapting the same technology that powers VS Code's "Go to Definition": the **Language Server Protocol (LSP)** concepts. We don't run a full heavy Language Server; we implemented a "Headless" version using **Tree-Sitter** and **SQLite**.

## 2. The Stack

### A. The Engine: Tree-Sitter
*   **What it is:** A parser generator tool and an incremental parsing library. It builds a concrete syntax tree for a source file and can efficiently update the syntax tree as the source file is edited.
*   **Why we use it:** It is **fault-tolerant**. Unlike Python's built-in `ast` module, Tree-Sitter allows us to parse code even if it has syntax errors, preserving the valid parts. It provides precise byte-ranges for every symbol.
*   **Implementation:** `llmc.rag.schema.PythonTreeSitterSchemaExtractor`

### B. The Index: Graph SQLite
*   **What it is:** A highly optimized SQLite database (`.llmc/rag_graph.db`) that stores the "Connectome" of the codebase.
*   **Entities:** Classes, Functions, Methods.
*   **Relationships:** `calls`, `inherits_from`, `imports`.
*   **Optimization:** We do **not** store full code in the DB. We store **Pointers** (file path + start/end lines).

### C. The Map: Skeletonization
*   **Problem:** We cannot feed 1,000 files into the Context Window.
*   **Solution:** We generate a **Skeleton View** (or "Header File").
*   **How:** We use Tree-Sitter to recursively walk the file. We keep every class definition, function signature, and docstring. We **delete** the implementation bodies.
*   **Result:** A 500-line implementation file becomes a 20-line map. The LLM sees *what* is available without wasting tokens on *how* it works.

### D. The Scope: Sniper Reader
*   **Workflow:**
    1.  Agent sees `GraphDatabase.bulk_insert_nodes` in the Skeleton.
    2.  Agent wants to know *how* it works.
    3.  Agent calls `read("GraphDatabase.bulk_insert_nodes")`.
*   **Mechanism:** The tool queries the SQLite Graph Index for the symbol ID, retrieves the precise file path and line range, and reads *only* those bytes from disk.
*   **Benefit:** Zero hallucination navigation. The Agent snipes exactly the code it needs.

## 3. The "Dialectical Autocoding" Workflow

1.  **Startup Injection:**
    *   The Agent initializes.
    *   System Prompt is injected with `llmc-rag skeleton`.
    *   **State:** The Agent now knows every function in the project. It "knows" the codebase structure intimately.

2.  **Task Execution:**
    *   User asks: "Refactor the bulk insert logic."
    *   Agent (referencing Skeleton): "I see `bulk_insert_nodes` in `graph_db.py`. I need to see the implementation."
    *   Agent Action: `read("llmc.rag.graph_db.GraphDatabase.bulk_insert_nodes")`.
    *   System Output: Returns the 20 lines of implementation code.

3.  **Refactoring:**
    *   Agent makes changes.
    *   Because it sees the Graph, it knows `bulk_insert_nodes` is called by `test_graph_staleness.py`.
    *   Agent proactively updates tests (using Graph lineage data).

## 4. References & Inspiration

This architecture is not invented here; it adapts industrial-grade patterns for Agentic RAG.

1.  **Language Server Protocol (LSP)** (Microsoft)
    *   The standard for how IDEs talk to language tools. We borrowed the concept of "Symbols" and "Goto Definition".
    *   *Reference:* [microsoft.github.io/language-server-protocol](https://microsoft.github.io/language-server-protocol/)

2.  **Tree-Sitter** (GitHub)
    *   The parsing engine used by Atom, Neovim, and GitHub.com for syntax highlighting and navigation.
    *   *Reference:* [tree-sitter.github.io](https://tree-sitter.github.io/tree-sitter/)

3.  **SCIP (Sourcegraph Cross-Language Indexing Protocol)**
    *   An evolution of LSIF. Sourcegraph uses this to index massive codebases for semantic search. Our SQLite graph is a simplified, pragmatic implementation of a SCIP index.
    *   *Pivot Decision:* We chose *not* to use the SCIP protobuf format directly (too heavy/binary/complex) and instead built a bespoke SQLite schema that mirrors its semantic capability but remains queryable with standard SQL.
    *   *Reference:* [github.com/sourcegraph/scip](https://github.com/sourcegraph/scip)

4.  **"Skeletonization" (Generic Concept)**
    *   Also known as "Stubs" (Python `.pyi` files) or "Header Files" (C/C++ `.h` files).
    *   We generate these dynamically to give the LLM the "Interface" without the "Implementation".

## 5. Why "Enrichment Summaries" Failed

We previously attempted to have an LLM read every file and write a summary paragraph ("Enrichment").

*   **The Fallacy:** "If we summarize code, the LLM can search the summaries."
*   **The Reality:** Code *is* the best summary of itself, provided you strip the implementation details. A docstring + function signature is infinitely more precise than an AI's attempt to describe it in English.
*   **The Fix:** We replaced **Subjective Summaries** (AI generated) with **Objective Skeletons** (Parser generated).

---
*Generated by the Architect from Hell for LLMC v0.9.x*
