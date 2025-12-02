#!/usr/bin/env bash
# scripts/bench_full.sh — run full suite
set -euo pipefail
export LLMC_TE_EXE="${LLMC_TE_EXE:-scripts/te}"
PYTHONPATH=. python3 -m llmc_mcp.benchmarks
