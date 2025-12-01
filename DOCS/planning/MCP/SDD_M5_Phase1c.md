
# SDD — M5 Phase‑1c (Tool List + Metrics Smoke Tests)
**Scope:** Add resilient smoke tests that verify:
- the MCP tool registry includes `te_run`, `repo_read`, and `rag_query`
- the `get_metrics` tool is callable and returns a dictionary‑like payload

## Goals
- Zero‑flake checks that work across small API variations (registry attr vs function).
- Keep assertions intentionally light to avoid coupling to internal schemas.

## Non‑Goals
- Full integration over MCP stdio or Claude Desktop.
- Deep metrics content validation (covered elsewhere).

## Risks & Mitigations
- **Different registry exposure names** → test tries `TOOL_REGISTRY`, `tool_registry`, and `get_tool_registry()`.
- **Different get_metrics signatures** → test tries `get_metrics()` then `get_metrics({})` and skips gracefully if unknown.
