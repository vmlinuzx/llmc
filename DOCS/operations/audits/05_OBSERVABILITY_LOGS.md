# Audit Charter: Observability & Logging

**Target Systems:**
*   `llmc/rag/` (Enrichment logs)
*   `llmc/rag_daemon/` (Service logs)
*   `logs/` (The output artifacts)

**The Objective:**
Logs must be a narrative of system state, not a dumping ground for debug prints. When the system fails, the logs must explain *why* within 3 seconds of reading.

**Specific Hunting Grounds:**

1.  **The Signal-to-Noise Ratio:**
    *   Run a full enrichment cycle. Count the lines of logs.
    *   **The "Trace in Info" Sin:** Are we logging high-frequency events (like "Processing span 1042...") at `INFO` level? Move them to `DEBUG`.
    *   **The "Print" Crime:** Grep for `print(`. Every `print` statement in library code is a failure of engineering. It bypasses log routing, formatting, and persistence.

2.  **The Structured Truth:**
    *   Are logs machine-parseable? (JSON lines or consistent key-value pairs).
    *   Do log messages contain context?
        *   *Bad:* `Error processing file.` (Which file? What error?)
        *   *Good:* `Processing failed. file="src/main.py" error="Timeout" attempts=3`

3.  **The Silent Failure (Swallowed Exceptions):**
    *   Look for `except Exception: pass`. This is code cancer.
    *   Look for `except Exception as e: print(e)`. This destroys the stack trace.
    *   **Requirement:** Every exception caught must be either handled explicitly (and logged as `INFO`/`WARN`) or re-raised. If it's a crash, we need the stack trace.

4.  **The "User vs. System" Split:**
    *   Are we leaking internal implementation details to the user console?
    *   `stderr` is for user-facing errors. `logs/llmc.log` is for the Architect. Do not confuse them.

**Command for Jules:**
`audit_logs --persona=architect --target=llmc/rag`
