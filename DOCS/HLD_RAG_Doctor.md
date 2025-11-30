# HLD – RAG Doctor & Service Log Integration

## Goal

Add a lightweight "RAG doctor" that can:
- Inspect the RAG SQLite index for basic health.
- Report pending work (enrichments, embeddings).
- Surface obvious data anomalies (orphan enrichments).
- Be callable both from the CLI (`rag doctor`) and from the RAG service loop,
  so you see health snapshots **between enrichment and embedding passes**.

This is **read-only** and designed to be:
- Safe (no schema changes, no writes).
- Cheap (a few SELECT COUNT(*) queries).
- Noisy in logs on purpose: "more spam for the logs, more blood for the blood god".

## Components

1. `tools.rag.doctor`
   - New module that opens the RAG DB for a repo and computes:
     - file / span / enrichment / embedding counts
     - pending enrichments
     - pending embeddings (profile `default`)
     - orphan enrichments (enrichments with no backing span)
   - Returns a JSON-friendly `dict` report.
   - Provides `format_rag_doctor_summary()` for a single-line log summary.

2. `rag doctor` CLI
   - Reuses the same `run_rag_doctor()` function.
   - Prints either JSON (`--json`) or a human summary line.
   - In verbose mode, also prints the top files with pending enrichments.

3. Service integration (`tools.rag.service.RAGService.process_repo`)
   - After Step 2 (enrichment) and before Step 3 (embeddings),
     the service calls `run_rag_doctor()` and logs the summary line.
   - This gives you a heartbeat of "how full is the backlog" every cycle.

## Out of Scope

- No schema migrations.
- No auto-repair of data (just detection/reporting).
- No cross-repo aggregation; doctor runs per repo.
