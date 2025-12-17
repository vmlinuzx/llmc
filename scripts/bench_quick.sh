#!/usr/bin/env bash
# scripts/bench_quick.sh — run quick benchmark (te_echo)
set -euo pipefail
docker compose --project-directory . -f docker/deploy/mcp/docker-compose.yml run --rm llmc-mcp bash -lc 'PYTHONPATH=. python3 -m llmc_mcp.benchmarks --quick'
