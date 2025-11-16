# LLMC RAG Nav — Task 1 System Overview (Index Status Layer)

This document summarizes the first slice of the **RAG Nav** subsystem,
focused purely on **index status metadata**.

## Purpose

Downstream components (indexer, daemon, MCP tools, TUIs) need to know:

- Is the schema-enriched graph/index for this repo **fresh**?
- When was it last built?
- Which commit was it built at?
- Which graph/index schema version does it use?
- Did the last attempt to build it fail? If so, why?

Task 1 introduces a small, durable status layer that answers those
questions without changing any existing behavior in LLMC.

## Key Concepts

- **IndexStatus**
  - A dataclass representing the status metadata for a single repo.
  - Encoded as JSON on disk.
- **Status File**
  - Lives at `${REPO_ROOT}/.llmc/rag_index_status.json`.
  - Written atomically to avoid partial or corrupt writes.
- **Status API**
  - Simple Python functions to load and save the status.

## How It Fits into the Bigger Picture

Later tasks will use this status layer to implement:

- A **Context Gateway** that decides whether to route queries to RAG
  graph tools or local fallbacks.
- A **where-used / lineage** toolset that depends on the freshness of
  the graph artifacts.
- MCP tool surfaces that can report index health to external callers.

For now, this layer is self-contained and safe to adopt without
any impact on existing scripts or services.

## Files Introduced

- `tools/rag_nav/__init__.py`
- `tools/rag_nav/models.py`
- `tools/rag_nav/metadata.py`
- `tests/test_rag_nav_metadata.py`

## Operational Notes

- The status file is not created automatically yet; it will be written
  by future indexer/graph-builder code (Task 2+).
- Removing the status file is safe; callers will interpret this as
  “no status/unknown freshness”.
- The design assumes Git is available for populating `last_indexed_commit`,
  but does not require it — `None` is allowed.

