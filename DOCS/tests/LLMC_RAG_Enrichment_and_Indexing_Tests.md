# LLMC RAG Enrichment & Indexing — Test Plan for Codex

This document describes **high-value tests** for the enrichment, AST chunking,
schema-enriched metadata, and index maintenance pieces that feed the RAG core
(`scripts/rag/ast_chunker.py`, `scripts/rag/index_workspace.py`,
`tools.rag.enrichment`, `tools.rag.schema`, `tools.rag.graph`, and related helpers).

## 1. AST Chunker & Span Extraction

- Language coverage:
  - Python, shell scripts, and Markdown files are all chunked into spans that
    align with human-understandable units (functions, classes, sections).
- Structural boundaries:
  - Chunks do not cut through the middle of function definitions or Markdown headings.
  - Leading/trailing whitespace is normalized.
- Robustness to syntax errors:
  - Files with syntax errors still produce best-effort spans and do **not** crash the pipeline.
  - Syntax errors are logged with file + line information.

## 2. Schema-Enriched Metadata

- Core fields:
  - Each span includes: file path, language, span type (e.g., function, class, doc),
    line ranges, and stable IDs.
- Optional metadata:
  - When schema-enriched data is available (e.g., symbol name, module path, tags),
    it is attached correctly and round-trips through storage.
- Backwards compatibility:
  - Older spans without full schema data are still readable; missing fields get sensible defaults.

## 3. Graph Building & Where-Used Metadata

- Node coverage:
  - Every indexed file appears at least once in the graph artifact (e.g., `.llmc/rag_graph.json`).
- Edge construction:
  - Obvious references (imports, function calls, class usage) result in edges between nodes.
- Self-consistency:
  - Graph nodes reference only known files/spans; no dangling references.
- Corrupt graph:
  - A corrupt or partially written graph file results in a clear error and safe fallback behavior
    (e.g., “graph disabled, search still works”).

## 4. Index Workspace Script Behavior

- Fresh workspace:
  - `index_workspace.py` on a clean repo creates all expected artifacts:
    - `.rag/llmc.sqlite`,
    - `.llmc/rag_index_status.json`,
    - `.llmc/rag_graph.json` (when enabled).
- Incremental re-run:
  - Re-running the script without changes results in a no-op with minimal work.
  - Changing one file results in only that file being re-processed.
- Failure injection:
  - Simulated exceptions in enrichment or graph building:
    - Are logged with clear context.
    - Do not leave half-written artifacts (atomic write semantics).

## 5. Quality Labels & Span Health

- Quality metrics:
  - Spans include quality hints or flags (where supported) such as “short”, “placeholder”, or “OK”.
- CJK vs non-CJK handling:
  - The classifier distinguishes CJK/English correctly, especially for mixed content.
- Downstream impact:
  - Low-quality spans are either:
    - Filtered out of default search,
    - Or clearly marked for the caller to de-prioritize.

## 6. Index Status Metadata (`rag_index_status.json`)

- Round-trip:
  - Saving an `IndexStatus` record and re-loading it returns the same data.
- Missing file:
  - When the status file does not exist, callers see `None` / a documented “no status” value.
- Corrupt file:
  - Corrupt JSON is handled gracefully:
    - The system logs the problem,
    - Falls back to a safe default,
    - Does not crash the daemon or indexing script.

## 7. Large Repo & Performance Sanity

- Large workspace:
  - Running the enrichment/index pipeline on a repo with thousands of files:
    - Completes within a reasonable time (configurable threshold).
    - Does not explode RAM use.
- Streaming behavior:
  - Intermediate state is flushed periodically, not only at the very end,
    so long runs can be monitored and recovered.

## 8. End-to-End Enrichment + RAG Verification

- Known symbol scenario:
  - Add a small, new module with a distinctive symbol and docstring.
  - Run the enrichment/index pipeline.
  - Confirm:
    - The graph shows the new file and symbol.
    - A RAG query for that symbol finds the correct span + docstring.
- Tamper detection:
  - Intentionally remove or corrupt part of the enrichment output.
  - Verify:
    - A subsequent indexing run repairs or flags the damage.
    - The Ruthless Testing Agent gets enough signal to mark this as a failure.
