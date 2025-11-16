# LLMC RAG Core Service & Search — Test Plan for Codex

This document describes **high-value tests** Codex (or another agent) should implement and run
for the LLMC RAG core service, search, and planner layers (`tools.rag.*`, `scripts/rag/rag_server.py`,
and the `llmc-rag` CLI surface).

## 1. Config & CLI Wiring

- `llmc-rag --help` exits 0 and shows top-level commands (index, search, explain, debug, etc.).
- Each subcommand (`index`, `search`, `plan`, `service`, etc.):
  - Accepts `--config` and falls back to default config when omitted.
  - Rejects unknown flags with a clear error and non-zero exit code.
- Misconfigured config (missing required keys, invalid types) produces:
  - A short, actionable error on stderr.
  - Non-zero exit code, no partial side-effects (no half-written DB).

## 2. Database & Index Schema

- Fresh index creation:
  - Starting with an empty workspace, running `llmc-rag index` creates the SQLite DB in `.rag/llmc.sqlite`.
  - Tables for files, spans/chunks, embeddings, and metadata exist with expected columns.
- Idempotent re-index:
  - Running `llmc-rag index` twice without file changes does **not** duplicate rows.
  - Timestamps or version markers show “no-op” behavior when nothing changed.
- Corrupt DB behavior:
  - Intentionally corrupt the DB file and verify:
    - The process refuses to serve queries from it.
    - A clear diagnostic is logged.
    - There is an option/flag or documented path to rebuild.

## 3. Embeddings & Caching

- Happy path:
  - A small set of documents is embedded once; subsequent runs for the same content
    reuse cached embeddings rather than re-embedding.
- Provider errors:
  - Simulate rate-limit / network errors from the embedding provider:
    - Backoff & retry behavior is respected where configured.
    - Failures are logged and surfaced, not silently swallowed.
- Determinism:
  - For a given provider + configuration, embedding vectors for the same input
    (same text, same language) are stable across runs.

## 4. Enrichment & Indexing Pipeline

- File discovery:
  - Only files matching configured include/exclude patterns are indexed.
  - Hidden directories, virtualenvs, and large binary files are skipped.
- Span extraction:
  - For code files, spans are created at a reasonable granularity (e.g., functions, classes),
    not just arbitrary fixed-size chunks.
  - Neighboring spans avoid large overlaps while still maintaining context continuity.
- Incremental updates:
  - Modifying a single file only re-processes that file, not the entire workspace.
  - Deleted files are removed from the index and no longer appear in search results.

## 5. Planner & Context Trimmer

- Budget enforcement:
  - For a requested context budget (e.g., max N tokens/chars), the planner returns
    a bundle within that budget while still including the highest-scoring spans.
- Diversity of context:
  - When multiple files are relevant, the planner avoids picking 100% of context
    from a single file unless that file’s scores dominate.
- Degenerate queries:
  - Very short or empty queries:
    - Result in a clear error or a “nothing to do” response, not junk context.
  - Overly long queries:
    - Are trimmed safely and logged.

## 6. Search Ranking & Relevance

- Basic relevance:
  - Obvious keyword queries (exact symbol names, filenames) return correct hits in top positions.
- Semantic relevance:
  - Queries phrased in natural language (e.g., “how does the daemon backoff work?”)
    still retrieve the right implementation files and docs.
- Negative cases:
  - Queries for non-existent symbols return an explicit “no results” outcome,
    not confusing or low-confidence garbage.
- Stability:
  - Re-running the same query with the same index yields stable results
    (within expected non-determinism from ANN search, if any).

## 7. Service Layer & HTTP API (if enabled)

- Startup & health:
  - `rag_server.py` (or equivalent service entrypoint) starts successfully with default config.
  - `/health` (or equivalent) returns 200 and a simple JSON payload.
- Query endpoint:
  - Valid requests return JSON with results, timing, and scoring information.
  - Invalid requests (missing required fields, bad JSON) return 4xx with a useful error message.
- Concurrency:
  - Multiple concurrent requests do not crash the service and share the same underlying index.
  - Slow queries do not starve fast, trivial ones.

## 8. Logging & Observability

- Query logging:
  - Each query logs basic metadata: timestamp, query text, result count, latency.
- Error logging:
  - Errors include stack traces and enough context (repo, file path, operation) to debug.
- Log rotation:
  - Large logs are rotated or truncated via configuration or tooling, not allowed to grow unbounded.

## 9. End-to-End RAG Query Smoke Tests

- Cold-start:
  - From a clean repo, run:
    1. `llmc-rag index`
    2. `llmc-rag search` for a known symbol
  - Verify real, useful results are returned.
- “Ask the code” scenario:
  - Given a realistic question about LLMC’s behavior (e.g., “how does repo registration work?”),
    confirm the RAG pipeline returns the implementation files + key design docs that answer it.
- Failure reporting:
  - Any uncaught issue during an end-to-end run should produce:
    - Non-zero exit code,
    - A summary error message,
    - Logged details for the Ruthless Testing Agent to classify and report.
