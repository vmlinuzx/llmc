# Concurrency Demon Report: 2026-01-16

**Analysis Focus:** REST API v1, RAG Indexing/Searching, Daemon Operations.
**Modified Files Reviewed:** `llmc/rag/skeleton.py`, `llmc.toml`

## Summary

The RAG service daemon (`llmc/rag/service.py`) employs a hybrid concurrency model. The main processing loop is sequential, processing one repository at a time, which is safe. The "idle enrichment" feature, however, uses `asyncio` for high-throughput parallel processing.

The core design correctly anticipates and mitigates the most common SQLite concurrency issue ("database is locked") by serializing all database writes through a dedicated asynchronous queue. This demonstrates a strong understanding of `asyncio` concurrency patterns.

However, two medium-severity issues and one design inconsistency were identified that present risks to data integrity and reliability under specific conditions.

---

## Findings

### P2 - Medium: Non-Atomic Span Updates Risk Data Loss
- **File:** `llmc/rag/database.py`
- **Method:** `Database.replace_spans`

**Observation:**
The `replace_spans` method performs a critical differential update. It reads existing span hashes from the database, calculates which spans to add and delete in Python, and then executes `DELETE` and `INSERT` statements. This entire read-modify-write sequence is not wrapped in a single atomic transaction.

**Risk:**
If the service is terminated unexpectedly (e.g., process crash, `kill -9`) after the `DELETE` operation but before the subsequent `INSERT`s are committed, the existing data for any unchanged code blocks within the file will be permanently lost. This would require expensive re-enrichment and re-embedding for code that had not even changed.

**Recommendation:**
Wrap the entire logical operation within the `replace_spans` method in a single transaction to ensure atomicity.

```python
# llmc/rag/database.py

def replace_spans(self, file_id: int, spans: Sequence[SpanRecord]) -> None:
    # ... (existing setup code) ...

    with self.transaction() as conn: # Use existing context manager
        # Get existing span hashes for this file
        existing = conn.execute(
            "SELECT span_hash FROM spans WHERE file_id = ?", (file_id,)
        ).fetchall()
        existing_hashes = {row[0] for row in existing}

        # ... (rest of the safety guards and delta calculation) ...

        # Only delete spans that actually changed or were removed
        if to_delete:
            placeholders = ",".join("?" * len(to_delete))
            conn.execute(
                f"DELETE FROM spans WHERE span_hash IN ({placeholders})",
                list(to_delete)
            )

        # Only insert truly new or modified spans
        if new_spans:
            conn.executemany(
                # ... (existing INSERT statement) ...
            )
```

### P2 - Medium: Inconsistent and Non-Concurrent Failure Tracking
- **Files:** `llmc/rag/service.py`, `llmc/rag/async_enrichment.py`
- **Class:** `FailureTracker`

**Observation:**
1.  The main sequential processing loop in `service.py` uses a `FailureTracker` class to persistently record enrichment failures in a separate SQLite database (`rag-failures.db`). This prevents repeated attempts on permanently failing items.
2.  The high-performance concurrent idle enrichment path in `async_enrichment.py` **does not use this `FailureTracker`**. It only prints errors to stdout, meaning failures during idle runs are not persistently tracked.
3.  The `FailureTracker` class itself is not safe for concurrent use. It creates a single `sqlite3` connection in its constructor and does not use any locking, making it susceptible to the same "database is locked" or threading errors that were successfully mitigated for the main database.

**Risk:**
This design inconsistency leads to reduced reliability. Failures in the idle enrichment mode are not remembered, causing the service to waste resources and LLM calls by repeatedly attempting to process spans that may be permanently problematic. If the `FailureTracker` were to be used from the concurrent code path as-is, it would introduce race conditions or locking errors.

**Recommendation:**
1.  **Make `FailureTracker` Concurrency-Safe:** Add a `threading.Lock` to the `FailureTracker` class to serialize access to its database connection. All public methods should acquire this lock.
2.  **Integrate Failure Tracking into Async Path:** Modify the `enrich_span_async` function in `async_enrichment.py` to accept the `FailureTracker` instance and record failures to it, ensuring consistent reliability across all operation modes.

---

## Conclusion

The concurrency model is generally robust, especially the `asyncio` implementation for idle enrichment. The identified issues do not point to a fundamental architectural flaw but rather to specific areas where atomicity and reliability can be significantly improved. Addressing the non-atomic `replace_spans` operation and unifying the failure tracking logic will make the RAG service more resilient and efficient.
