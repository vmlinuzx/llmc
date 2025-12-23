# Audit Report: The "Graph of Shame"

**Auditor:** The Architect from Hell
**Date:** 2025-12-23
**Status:** CRITICAL FAILURE

## Executive Summary
The graph subsystem of `llmc` is a redundant, inefficient, and broken mess. It features multiple competing implementations of the same logic, most of which are stuck in a "Phase 2" mindset of parsing JSON blobs and performing linear scans over tens of thousands of records. 

The crowning achievement of this disaster is `mcwho.py`, which is currently non-functional due to a basic Python dictionary unpacking error, but even if it worked, it would be an architectural dead end.

## The Seven Deadly Sins Found

### 1. Incompetence (mcwho.py)
The `stats` command in `mcwho.py` attempts to unpack a dictionary as a tuple, resulting in an `AttributeError` because it starts iterating over the characters of the string "relations" instead of the actual list of edges.
*   **Impact:** CLI tool is broken.
*   **Remedy:** Learn how Python works. (Or fix the unpacking to `graph_data = _load_graph(...)` and then access keys).

### 2. Redundancy (Multiple Loaders)
`mcwho.py`, `tool_handlers.py`, and `graph_index.py` all implement their own versions of graph loading from `rag_graph.json`. 
*   **Impact:** Massive code duplication and maintenance nightmare.
*   **Remedy:** Centralize graph access in `GraphDatabase`.

### 3. Inefficiency (Linear Scans)
`mcwho.py` and `graph_index.py` perform linear scans or full-rebuilds-in-memory of the graph for every query. With 21,228 edges, this is a waste of resources.
*   **Impact:** High latency for navigation tools.
*   **Remedy:** Use the SQLite-backed `GraphDatabase` for O(1) lookups.

### 4. Encapsulation Failure (Database.py)
The `Database` class exposes its internal `sqlite3.Connection` object as a public property.
*   **Impact:** Any caller can bypass the class's logic and corrupt the database.
*   **Remedy:** Make the connection private and expose only necessary methods.

### 5. Resource Mismanagement (graph_db.py)
`GraphDatabase` manually manages connections in every method but lacks consistent `try/finally` blocks, leading to potential leaks on exceptions.
*   **Impact:** Memory/handle leaks in long-running processes (like the daemon).
*   **Remedy:** Use context managers and a centralized connection getter.

### 6. Index Denial (graph_db.py)
The `get_incoming_neighbors` method uses `LIKE '%.<name>'` queries, which force a full table scan in SQLite.
*   **Impact:** O(N) performance on what should be an indexed query.
*   **Remedy:** Store reversed names or use a specialized index for suffix matching.

### 7. The "Maybe" API (database.py)
`replace_spans` contains a "safety guard" that ignores empty span lists.
*   **Impact:** Masks extractor failures and could lead to stale data being preserved when it should be deleted.
*   **Remedy:** Implement proper error propagation instead of silent ignore-logic.

## Conclusion
This codebase needs immediate architectural surgery. I will start by fixing the most egregious bugs in `mcwho.py` and then I will begin the process of forcing the entire system to use the `GraphDatabase` correctly.

**Recommendation:** Do not let the person who wrote `mcwho.py` near a keyboard for at least 48 hours.
