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

---

## Audit Run: 2025-12-23

**Execution:**
- `python3 -m llmc.rag.cli stats` and `python3 -m llmc.rag.cli enrich --execute --limit 5`
- Index already present

**Log Line Counts Post-Run:**
| File | Lines |
|------|-------|
| `logs/enrichment_metrics.jsonl` | 1,837 |
| `logs/enrichment_router_metrics.jsonl` | 5,547 |
| `logs/planner_metrics.jsonl` | 5 |
| `logs/run_ledger.log` | 15,944 |

**Observation:** Log artifacts did not update during the run (mtimes still 2025-12-03/2025-12-18). The enrichment cycle emitted to stdout and left `logs/` untouched.

---

## Findings

### 🔴 CRITICAL: Enrichment CLI is an Observability Black Hole

**Issue:** `rag.cli enrich` produces no structured log output—just per-span print spam. This is "Trace in Info" and the "Print Crime" rolled into one.

**Evidence:**
- `llmc/rag/cli.py:289` - CLI prints directly
- `llmc/rag/enrichment_pipeline.py:687` - `_log_enrichment_success()` uses `print()`
- `llmc/rag/workers.py:104` - Workers print status

**Fix:** Route to a logger and emit JSONL into `logs/`.

---

### 🔴 HIGH: Corrupt Log Ledger

**Issue:** `logs/run_ledger.log:1` is malformed JSON (missing `{`). The ledger is already corrupt and parsers will choke.

**Fix:** Atomic append with a single write + lock, and validate on write.

---

### 🔴 HIGH: Silent Swallow Exceptions

**Issue:** Exception handlers hide failure modes in the watcher and daemon state loader. This is the "Silent Swallow" sin.

**Evidence:**
- `llmc/rag/watcher.py:73` - Exception caught, not logged
- `llmc/rag/watcher.py:95` - Same pattern
- `llmc/rag_daemon/state_store.py:24` - Silent failure

**Fix:** Log with context + stack trace, or re-raise.

---

### 🟡 MEDIUM: Daemon Logging is Plain Text

**Issue:** Daemon logging is plain text with no structured fields. CLI errors go to stdout, blurring user vs system channels.

**Evidence:**
- `llmc/rag_daemon/logging_utils.py:11` - Unstructured formatter
- `llmc/rag_daemon/main.py:118` - Print to stdout
- `llmc/rag_daemon/main.py:185` - Same pattern

**Fix:** JSON logging + stderr for user-facing failures.

---

### 🟡 MEDIUM: Planner Metrics Lack Context

**Issue:** Planner metrics lack timestamp/repo context, so correlation with enrichment runs is guesswork.

**Evidence:**
- `llmc/rag/planner.py:208` - Metrics without timestamp
- `llmc/rag/planner.py:296` - No repo_root field

**Fix:** Add `timestamp`, `repo_root`, and a `request_id`/`correlation_id`.

---

### 🟢 LOW: Indexer/DB Helpers Bypass Logging

**Issue:** Indexer/DB helpers still print errors and drop stack traces, bypassing the logging system.

**Evidence:**
- `llmc/rag/indexer.py:155` - `print()` on error
- `llmc/rag/enrichment_db_helpers.py:130` - Same pattern

**Fix:** Use the logger with structured context.

---

## Remediation Priority

| Priority | Issue | Effort | Owner |
|----------|-------|--------|-------|
| **P0** | Corrupt ledger fix | 2h | - |
| **P0** | Enrichment CLI → JSONL logger | 4h | - |
| **P1** | Silent swallow fixes (3 files) | 2h | - |
| **P1** | Daemon JSON logging | 3h | - |
| **P2** | Planner context fields | 1h | - |
| **P2** | Indexer/DB logger migration | 2h | - |

**Total Estimated Effort:** 14 hours

---

## Resolution

**SDD Created:** `DOCS/planning/SDD_Observability_Logging_Hardening.md`

**Rollout Plan (from SDD):**
- Phase 0: Add logging utility + tests
- Phase 1: Replace print usage in rag pipeline and workers
- Phase 2: Update planner metrics fields and daemon logging
- Phase 3: Ledger migration and integrity checks

**Status:** 🟢 SDD Complete - Ready for Implementation
