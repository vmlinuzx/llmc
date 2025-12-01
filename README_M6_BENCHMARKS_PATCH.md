
# LLMC — M6 Benchmarks Patch Bundle
Adds a tiny benchmark harness:
- `python -m llmc_mcp.benchmarks --quick`
- `python -m llmc_mcp.benchmarks --cases te_echo,repo_read_small,rag_top3`

Outputs CSV to `./metrics` (or `LLMC_BENCH_OUTDIR`).

Includes tests and two helper scripts: `scripts/bench_quick.sh`, `scripts/bench_full.sh`.
