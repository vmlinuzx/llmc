
#!/usr/bin/env bash
# scripts/smoke_mcp_in_container.sh — quick container bring-up
set -euo pipefail
docker compose -f deploy/mcp/docker-compose.yml up --build
