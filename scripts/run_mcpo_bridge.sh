#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCPO_CONFIG="$ROOT/mcp/mcpo.config.json"
CONFIG_BASE="${XDG_CONFIG_HOME:-$HOME}"
CONFIG_DIR="${CONFIG_BASE}/.claude-server-commander"
CONFIG_FILE="${CONFIG_DIR}/config.json"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

ensure_desktop_commander_config() {
  mkdir -p "$CONFIG_DIR"

  if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "[run_mcpo_bridge] Desktop Commander config missing, running setup..."
    desktop-commander setup --no-onboarding >/dev/null 2>&1 || true
  fi

  if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "[run_mcpo_bridge] Failed to create Desktop Commander config at $CONFIG_FILE" >&2
    exit 1
  fi

  local tmp
  tmp="$(mktemp)"
  trap 'rm -f "$tmp"' EXIT

  jq --arg root "$ROOT" '
    .allowedDirectories = (
      ((.allowedDirectories // []) + [$root])
      | map(.)
      | unique
    )
    | .telemetryEnabled = false
    | .defaultShell = "/bin/bash"
  ' "$CONFIG_FILE" >"$tmp"

  mv "$tmp" "$CONFIG_FILE"
  trap - EXIT
}

require_cmd mcpo
require_cmd desktop-commander
require_cmd jq

if [[ ! -f "$MCPO_CONFIG" ]]; then
  echo "[run_mcpo_bridge] Expected MCPO config missing at $MCPO_CONFIG" >&2
  exit 1
fi

ensure_desktop_commander_config

HOST="${MCP_HOST:-127.0.0.1}"
PORT="${MCP_PORT:-5002}"
API_KEY="${MCP_API_KEY:-}"
LOG_LEVEL="${MCP_LOG_LEVEL:-info}"

cmd=(mcpo --host "$HOST" --port "$PORT" --config "$MCPO_CONFIG" --hot-reload --log-level "$LOG_LEVEL")

if [[ -n "$API_KEY" ]]; then
  cmd+=(--api-key "$API_KEY" --strict-auth)
fi

echo "[run_mcpo_bridge] Starting MCPO on ${HOST}:${PORT} using $MCPO_CONFIG"
exec "${cmd[@]}"
