
# Agent Implementation Prompt — M5 Phase‑1b (Copy/Paste)
You are applying a small follow‑up patch to LLMC.

## Objective
Add `repo_read` and `rag_query` wrappers that call the TE CLI through `te_run`, then wire them into the MCP tool registry.

## Steps
1) Create feature branch
```
git checkout -b feat/m5-phase1b-repo-rag
```

2) Add files
- `llmc_mcp/tools/te_repo.py`
- `llmc_mcp/tools/test_te_repo.py`
- `DOCS/planning/MCP/SDD_M5_Phase1b.md`
- `DOCS/planning/MCP/IMPL_SDD_M5_Phase1b.md`

3) Wire registry in the server
```
from llmc_mcp.tools.te import te_run
from llmc_mcp.tools.te_repo import repo_read, rag_query

TOOL_REGISTRY["te_run"] = te_run
TOOL_REGISTRY["repo_read"] = repo_read
TOOL_REGISTRY["rag_query"] = rag_query
```

4) Run tests
```
PYTHONPATH=. python -m llmc_mcp.tools.test_te_repo
```

5) Commit & PR
```
git add .
git commit -m "M5 Phase-1b: add TE wrappers repo_read/rag_query with normalized JSON envelope + tests"
git push origin feat/m5-phase1b-repo-rag
```
Open PR with results and follow‑ups.

## Follow‑ups
- Phase‑2: Dockerfile, compose, entrypoint.
