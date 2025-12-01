
#!/usr/bin/env bash
# scripts/smoke_te.sh — run TE wrapper tests inside container
set -euo pipefail
docker compose -f deploy/mcp/docker-compose.yml run --rm llmc-mcp   bash -lc 'PYTHONPATH=. python -m llmc_mcp.tools.test_te && PYTHONPATH=. python -m llmc_mcp.tools.test_te_repo'
