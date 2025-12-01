
# Implementation Notes — M6 Benchmarks
## Files
- `llmc_mcp/benchmarks/runner.py`
- `llmc_mcp/benchmarks/__main__.py`
- `llmc_mcp/benchmarks/test_runner.py`
- `scripts/bench_quick.sh`
- `scripts/bench_full.sh`

## Run
```
PYTHONPATH=. python -m llmc_mcp.benchmarks --quick
PYTHONPATH=. python -m llmc_mcp.benchmarks --cases te_echo,repo_read_small,rag_top3
```

## CI Suggestion
- Add the quick bench to a nightly or optional workflow; do not gate PRs on it.
