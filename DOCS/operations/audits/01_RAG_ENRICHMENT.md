# Audit Charter: RAG & Enrichment

**Target Systems:**
*   `llmc/rag/` (The core pipeline)
*   `llmc/rag_daemon/` (The scheduler)
*   `llmc/rag_repo/` (The repository manager)

**The Objective:**
Identify where we are burning tokens, CPU, and wall-clock time in the pursuit of "context."

**Specific Hunting Grounds:**

1.  **The Pipeline Bloat:**
    *   Look at `EnrichmentPipeline`. Are we passing massive objects around?
    *   Are we serializing to JSON and back unnecessarily between the Router and the Backend?

2.  **The Embedding Sinkhole:**
    *   Inspect `run_embed`. Are we batching correctly?
    *   Are we re-embedding identical text just because a metadata field changed? (The "Content-Hash vs. Span-Hash" confusion).

3.  **The Database Stranglehold:**
    *   Review `llmc/rag/database.py`.
    *   Look for N+1 query patterns in `fetch_all_spans` or `pending_enrichments`.
    *   Are we fetching `TEXT` columns (file content) when we only need `id` and `hash`?

4.  **The Scheduler's Sleep Apnea:**
    *   Check `llmc/rag_daemon/scheduler.py`.
    *   Does the scheduler wake up too often? Does it sleep too long?
    *   Does it efficiently handle the "nothing to do" state, or does it burn 100% CPU checking 50 empty queues?

**Command for Jules:**
`audit_rag --persona=architect --target=llmc/rag`
