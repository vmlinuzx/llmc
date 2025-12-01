
#!/usr/bin/env bash
set -euo pipefail

# If invoked with "bash" or another command, exec it
if [[ "${1:-}" != "" && "${1:-}" != "server" ]]; then
  exec "$@"
fi

# Export legacy TE_* alongside namespaced LLMC_TE_* for compatibility
export TE_AGENT_ID="${LLMC_TE_AGENT_ID:-${TE_AGENT_ID:-agent-docker}}"
export TE_SESSION_ID="${LLMC_TE_SESSION_ID:-${TE_SESSION_ID:-docker-dev}}"
export TE_MODEL="${LLMC_TE_MODEL:-${TE_MODEL:-unknown}}"

# Observability defaults (override via env or TOML)
export LLMC_LOG_FORMAT="${LLMC_LOG_FORMAT:-json}"
export LLMC_LOG_DIR="${LLMC_LOG_DIR:-/logs}"
export LLMC_METRICS_DIR="${LLMC_METRICS_DIR:-/metrics}"

# Kick tires: run a tiny Python to show versions
python - << 'PY'
import sys, platform
print("LLMC container boot:", sys.version, platform.platform(), flush=True)
PY

# Start MCP server (stdio). Adjust if your server entry differs.
exec python -m llmc_mcp.server
