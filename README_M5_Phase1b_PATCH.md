
# LLMC — M5 Phase‑1b Patch Bundle
Adds `repo_read` and `rag_query` wrappers on top of `te_run`, plus tests and docs.

## Apply
Copy this archive into your repo root, then wire the new tools into your MCP tool registry.

## Test
```
PYTHONPATH=. python -m llmc_mcp.tools.test_te_repo
```

## Next
- Phase‑2: Dockerfile + docker-compose + entrypoint.
