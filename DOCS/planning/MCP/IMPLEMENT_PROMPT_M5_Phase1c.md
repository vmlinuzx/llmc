
# Agent Implementation Prompt — M5 Phase‑1c (Copy/Paste)
Objective: Add resilient smoke tests for tool visibility and metrics call.

## Steps
1) Feature branch
```
git checkout -b feat/m5-phase1c-smoke-tests
```

2) Add file
- `llmc_mcp/test_tools_visibility_and_metrics.py`

3) Run tests
```
PYTHONPATH=. python -m llmc_mcp.test_tools_visibility_and_metrics
```

4) Commit & PR
```
git add .
git commit -m "M5 Phase-1c: add smoke tests for tool registry and get_metrics"
git push origin feat/m5-phase1c-smoke-tests
```
