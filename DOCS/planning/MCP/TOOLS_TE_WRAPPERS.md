
# TE Wrapper Tools — API Overview
This document summarizes the MCP‑side wrapper tools that call your TE CLI.

## Tools
### te_run(args: Sequence[str], ctx: Optional[McpSessionContext], ... ) -> dict
Executes TE with enforced `--json`. Returns normalized envelope:
```
{"data": <parsed JSON or {"raw": "..."}>, "meta": {"returncode": int, "duration_s": float, "stderr": str, "argv": [...] }}
```

### repo_read(root: str, path: str, max_bytes: Optional[int] = None, ctx: Optional[McpSessionContext] = None) -> dict
Builds `["repo","read","--root",root,"--path",path,"--max-bytes",N?]` and calls `te_run`.

### rag_query(query: str, k: int = 5, index: Optional[str] = None, filters: Optional[dict] = None, ctx: Optional[McpSessionContext] = None) -> dict
Builds `["rag","query","--q",query,"--k",k?,"--index",name?,"--filters",json?]` and calls `te_run`.

## Notes
- All wrappers are side‑effect free at import time.
- Observability and session context are applied inside `te_run`.
- Filters are JSON‑encoded defensively; failures are logged and ignored.
