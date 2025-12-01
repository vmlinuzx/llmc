
# SDD — M6 Benchmarks (MCP-Side Harness)
**Scope:** Add a minimal, dependency-free benchmark runner that times MCP wrapper tools and writes CSV outputs.

## Goals
- Benchmark without requiring TE or Claude Desktop at runtime (monkeypatchable).
- Output CSV to `./metrics` by default (or `LLMC_BENCH_OUTDIR`).
- Cases:
  - `te_echo` — sanity
  - `repo_read_small` — IO path
  - `rag_top3` — RAG path

## Metrics
- `duration_s`: wall time per case
- `returncode`: subprocess/adapter code
- `data_bytes`: JSON-serialized size of the `data` payload

## Risks
- TE not present → harness still runs with patchable call sites.
- File system paths differ → output dir is created automatically.
