
# Agent Implementation Prompt — M5 Phase‑1 (Copy/Paste)
You are an engineering agent applying a small patch to the LLMC repo.

## Objective
Add the TE JSON wrapper tool `te_run` and tests, wire it into the MCP server's tool registry.

## Constraints
- Keep repo clean: no files at repo root beyond standards.
- Follow GitHub best practices: feature branch, small PR, CI green.

## Steps
1) Create feature branch
```
git checkout -b feat/m5-phase1-te-run
```

2) Add files
- `llmc_mcp/tools/te.py` (from patch)
- `llmc_mcp/tools/test_te.py` (from patch)
- `DOCS/planning/MCP/SDD_M5_Phase1.md`
- `DOCS/planning/MCP/IMPL_SDD_M5_Phase1.md`

3) Wire server registry
- Import and register `te_run` in the MCP server dispatch dictionary.
- Ensure `list_tools` shows `"te_run"`.

4) Run tests
```
PYTHONPATH=. python -m llmc_mcp.tools.test_te
PYTHONPATH=. python -m llmc_mcp.test_smoke   # should still pass
```

5) Commit
```
git add .
git commit -m "M5 Phase-1: add TE wrapper tool te_run with JSON envelope and tests"
git push origin feat/m5-phase1-te-run
```

6) Open PR
- Title: "M5 Phase‑1: TE JSON wrapper tool (`te_run`)"
- Description: Include scope, test results, and follow‑ups (Phase‑1b repo_read/rag_query).

7) After merge
- Tag pre-Docker milestone: `git tag m5-phase1` and `git push --tags`.
