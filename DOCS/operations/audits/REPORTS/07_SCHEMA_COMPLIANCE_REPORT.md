# Audit Report: Schema Compliance & Data Integrity
**Date:** 2025-12-23
**Auditor:** The Architect
**Status:** FAILED

## Executive Summary
The database schema management is a mess of "apply patch later" logic. The Python dataclasses (`SpanRecord`) promise data (imports) that the database (`spans` table) simply discards. We are maintaining two separate databases (`index_v2.db` and `rag_graph.db`) with zero referential integrity between them, relying on "hope" that symbol names match.

## 1. The Migration Swamp (`llmc/rag/database.py`)
The `SCHEMA` constant is a lie. It represents a version of the database from months ago. Every new connection triggers a cascade of `ALTER TABLE` statements because the base `CREATE TABLE` definitions are stale.

*   **Violation:** `SCHEMA` definition for `enrichments` is missing 6 columns (`tokens_per_second`, `eval_count`, etc.).
*   **Violation:** `SCHEMA` definition for `files` is missing `sidecar_path`.
*   **Violation:** `SCHEMA` definition for `spans` is missing `slice_type`, `slice_language`, `classifier_confidence`, `classifier_version`.
*   **Impact:** New installations execute 10+ unnecessary DDL operations on first startup.

## 2. The Data Loss (`llmc/rag/types.py` vs `llmc/rag/database.py`)
We are silently dropping data.

*   **Violation:** `SpanRecord` has a field `imports: list[str]`.
*   **Violation:** The `spans` table in SQLite has **no column** for imports.
*   **Violation:** `database.py::replace_spans` silently ignores `span.imports`.
*   **Impact:** Any logic relying on retrieving imports from the DB (e.g., dependency analysis after a restart) will fail or require re-parsing the file.

## 3. The Ghost Columns
We are storing data we never read.

*   **Violation:** `embeddings` table has `route_name` and `profile_name`.
*   **Violation:** `iter_embeddings` (the main reader) **does not select** these columns.
*   **Action:** Either remove them or update the reader to use them.

## 4. The Graph Split Brain
We run two disparate databases:
1.  `.rag/index_v2.db` (Spans, Enrichments, Embeddings)
2.  `.llmc/rag_graph.db` (Nodes, Edges - populated from JSON)

*   **Risk:** `rag_graph.db` is rebuilt from JSON (`rag_graph.json`), while `index_v2.db` is built from source. If `mcschema` (JSON generator) drifts from `database.py` (SQLite generator), the graph navigation tools (`mcwho`, `mcinspect`) will point to symbols that do not exist in the enrichment index.

## Recommendations

1.  **Update `SCHEMA` Constant:** creating a table should create the *current* version, not the version from 2024.
2.  **Fix `SpanRecord` persistence:** Serialize `imports` to JSON and store it in `spans`, or remove it from the Dataclass if it's not meant to be persisted.
3.  **Unify or Link DBs:** At minimum, ensure `rag_graph.db` nodes have a foreign key-like reference (e.g. `span_hash`) to `index_v2.db` to allow joining enrichment data into graph queries.

**Severity:** HIGH. Data loss (imports) and schema drift (migrations) are unacceptable.
