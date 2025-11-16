# LLMC RAG Nav — Task 4 System Overview (Context Gateway)

Task 4 is the "safety rail" for LLMC RAG Nav. It answers a simple
but crucial question before every query:

> "Is it safe to use the RAG graph, or should we fall back to the live repo?"

## Key Ideas

- **IndexStatus** (Task 1) tells us what the index *thinks* it knows.
- **Git HEAD** tells us where the repo actually is right now.
- The **Context Gateway** compares the two and returns a
  `RouteDecision`:
  - Use RAG vs. local fallback.
  - Freshness label: `"FRESH"`, `"STALE"`, or `"UNKNOWN"`.

## Behaviour Summary

- If the index is clearly fresh and matches HEAD:
  - Use RAG graph (`source="RAG_GRAPH"`, `freshness_state="FRESH"`).
- If the index is stale, rebuilding, errored, or mismatched:
  - Use live repo scan (`source="LOCAL_FALLBACK"`, `freshness_state="STALE"`).
- If we can't tell (no status, missing git info):
  - Use live repo scan (`source="LOCAL_FALLBACK"`, `freshness_state="UNKNOWN"`).

## Impact on Tools

- Search, where-used, and lineage still behave the same logically:
  - They find lines that contain the query/symbol and return snippets.
- But now they also:
  - Select between graph-based file lists and fresh directory walks.
  - Surface a clear provenance tag so callers can make informed choices.

## Why This Matters

- Prevents silent misuse of stale RAG data when the repo has moved on.
- Gives higher-level agents (MCP, TUIs, etc.) a simple signal for
  when to trust RAG vs. lean on local or brute-force strategies.
- Sets the stage for richer lineage and where-used semantics
  without risking correctness during the experimental phase.

