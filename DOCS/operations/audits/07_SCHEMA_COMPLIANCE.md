# Audit Charter: Schema Compliance & Data Integrity

**Target Systems:**
*   `llmc/rag/database.py` (The Source of Truth... allegedly)
*   `llmc/rag/graph_db.py` (The Graph Store)
*   `llmc/rag/schema.py` (The Data Models)
*   `.rag/index_v2.db` (The SQLite Artifact)

**The Objective:**
Ensure that what we *think* is in the database is actually what *is* in the database. Detect drift between Python code, SQL DDL, and runtime migrations.

**Specific Hunting Grounds:**

1.  **The Migration Swamp:**
    *   Inspect `database.py::_run_migrations`.
    *   Are we adding columns in Python that aren't in the `SCHEMA` constant?
    *   Are there "temporary" migrations from 2024 still running in 2025?
    *   *Sin:* Defined in `SCHEMA`, missing in `INSERT`, or vice versa.

2.  **The Orphanage:**
    *   Check for `spans` referencing non-existent `files`.
    *   Check for `enrichments` referencing non-existent `spans`.
    *   Although `FOREIGN KEY` constraints are enabled (`PRAGMA foreign_keys = ON`), verify they are actually respected during bulk inserts.

3.  **The Type Lie:**
    *   Review `SpanRecord` vs `spans` table.
    *   Are we storing booleans as integers? Integers as strings?
    *   Check `metadata` JSON blobs. Are they becoming unstructured dumping grounds?

4.  **The Ghost Columns:**
    *   Identify columns in `SCHEMA` that are **never** read or written by the Python code.
    *   *Action:* If it's dead, bury it.

5.  **Graph Integrity:**
    *   Check `llmc/rag/graph_db.py`.
    *   Ensure `nodes.id` consistency between the graph DB and the main index.
    *   Verify `edges` do not point to void IDs.

**Command for Jules:**
`audit_schema --persona=architect --target=llmc/rag`
