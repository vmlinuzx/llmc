
# SDD — M5 Phase‑1b (Repo/RAG Wrappers)
**Scope:** Add `repo_read` and `rag_query` wrappers that call TE via `te_run` and return normalized envelopes.

## Goals
- Thin, deterministic adapters over the TE CLI subcommands.
- No TE import at module import time; subprocess only.
- Stable return shape: `{"data": ..., "meta": ...}` consistent with Phase‑1a.

## Interfaces
### Tools
- `repo_read(root: str, path: str, max_bytes: Optional[int], ctx: Optional[McpSessionContext]) -> dict`
- `rag_query(query: str, k: int = 5, index: Optional[str] = None, filters: Optional[dict] = None, ctx: Optional[McpSessionContext]) -> dict`

### TE CLI Expectations (subject to your TE implementation)
- `te repo read --root ROOT --path PATH [--max-bytes N]`
- `te rag query --q QUERY [--k K] [--index NAME] [--filters JSON]`

## Risks & Mitigations
- **Filters serialization issues** → guarded JSON encode with warning.
- **CLI mismatch** → wrappers only build args; TE can add aliases/options later without breaking MCP code.

## Tests
- Arg-shape assertions via monkeypatched `te_run` (no subprocess dependency).
- Robustness when filters cannot be JSON-encoded.
