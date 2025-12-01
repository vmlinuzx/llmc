
# Agent Implementation Prompt — M6 Benchmarks (Copy/Paste)
Objective: Add the MCP-side benchmark harness and scripts.

## Steps
```
git checkout -b feat/m6-benchmarks
# add files from patch
PYTHONPATH=. python -m llmc_mcp.benchmarks --quick
PYTHONPATH=. python -m llmc_mcp.benchmarks --cases te_echo,repo_read_small,rag_top3
git add .
git commit -m "M6: add MCP-side benchmark harness and scripts"
git push origin feat/m6-benchmarks
```
Open PR with CSV sample and durations.
