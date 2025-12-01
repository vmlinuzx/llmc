
# SDD — M5 Phase‑1 (TE JSON Handshake & MCP Tool Surface)
**Scope:** Introduce `te_run` tool and stable JSON envelope for TE calls. No Docker yet.

## Goals
- MCP calls TE as a subprocess with enforced `--json` output.
- Namespaced session metadata env: `LLMC_TE_AGENT_ID`, `LLMC_TE_SESSION_ID`, `LLMC_TE_MODEL` (+ legacy fallback).
- Provide a thin wrapper module (`llmc_mcp/tools/te.py`) with normalized return: `{"data": ..., "meta": ...}`.
- Add isolated tests that mock subprocess (no TE runtime dependency).

## Non‑Goals
- Docker/compose (Phase‑2)
- `repo_read` / `rag_query` (Phase‑1b)

## Interfaces
### Env
- `LLMC_TE_EXE` (optional) — path/name of TE CLI. Default: `te`.

### Tool
- `te_run(args: Sequence[str], ctx: Optional[McpSessionContext], timeout: Optional[float], cwd: Optional[str], extra_env: Optional[Mapping[str,str]]) -> dict`

### Return Envelope
```json
{
  "data": { "...": "parsed JSON from TE or {'raw': '...'}" },
  "meta": {
    "returncode": 0,
    "duration_s": 0.123,
    "stderr": "",
    "argv": ["te","--json",...]
  }
}
```

## Risks & Mitigations
- **TE not installed** → Failure path returns `error: true` with stderr; does not crash MCP process.
- **Non‑JSON TE output** → We wrap as `{"raw": "..."}` to avoid parser failures.
- **Session leakage** → Namespaced LLMC vars; legacy duplicates for compatibility.

## Tests
- Inject `--json` and LLMC vars; assert envelope.
- Non‑JSON stdout transforms to `{'raw': ...}`.
- Subprocess error becomes meta `error: true`.
