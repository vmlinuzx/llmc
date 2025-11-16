# LLMC RAG Nav — Task 3 System Overview (RAG-only Tools)

Task 3 is where the RAG Nav subsystem starts to feel useful: it adds
search, where-used, and lineage-style queries over the codebase.

## What It Does

- Uses the `.llmc/rag_graph.json` file from Task 2 as a manifest of
  source files.
- Runs a simple, line-based substring search to find occurrences of
  a given query or symbol.
- Returns structured results (`SearchResult`, `WhereUsedResult`,
  `LineageResult`) that include snippets and locations.

## What It Does NOT Do (Yet)

- No real dependency graph traversal (lineage is still approximate).
- No freshness or fallback routing — all results are tagged with
  `source="RAG_GRAPH"` and `freshness_state="UNKNOWN"`.
- No MCP exposure; this is still CLI / Python API only.

## Usage Examples

From the repo root, after running `llmc-rag-nav build-graph`:

```bash
scripts/llmc-rag-nav search --repo . --query target_symbol
scripts/llmc-rag-nav where-used --repo . --symbol target_symbol
scripts/llmc-rag-nav lineage --repo . --symbol target_symbol --direction downstream
```

All commands emit JSON, which can be consumed by higher-level tools
or piped into jq for ad-hoc inspection.

## Role in the Bigger Plan

- Demonstrates that the RAG Nav graph + status plumbing works end-to-end.
- Provides a concrete surface for future improvements:
  - Swap naive search for graph-based where-used.
  - Layer on freshness-aware Context Gateway (Task 4).
  - Wire into MCP so other agents can call these tools safely.

