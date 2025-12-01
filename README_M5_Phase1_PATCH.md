
# LLMC — M5 Phase‑1 Patch Bundle
This bundle adds a TE subprocess wrapper tool (`te_run`) with enforced `--json`,
a normalized return envelope, and isolated tests.

## Apply
Copy the contents of this archive into your repo root (preserving paths),
then wire `te_run` into your MCP server's tool registry.

## Test
```
PYTHONPATH=. python -m llmc_mcp.tools.test_te
```

## Next
- Phase‑1b: add `repo_read` / `rag_query` wrappers and server wiring.
- Phase‑2: Dockerfile + docker-compose + entrypoint.
