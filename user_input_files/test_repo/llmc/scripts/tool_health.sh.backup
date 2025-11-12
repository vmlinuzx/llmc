#!/usr/bin/env bash
# tool_health.sh — Verify local CLI/MCP tools and emit a compact ToolCaps summary.
# Outputs:
#   - .codex/state/tools.json (detailed results)
#   - .codex/state/tools.env  (exports CLAUDE_TOOLCAPS="...")
# Usage:
#   llmc/scripts/tool_health.sh
# Env:
#   TOOLS_MANIFEST (optional): path to JSON manifest (default: .codex/tools.json)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$ROOT/.codex/state"
MANIFEST="${TOOLS_MANIFEST:-$ROOT/.codex/tools.json}"
OUT_JSON="$STATE_DIR/tools.json"
OUT_ENV="$STATE_DIR/tools.env"

mkdir -p "$STATE_DIR"

have_cmd() { command -v "$1" >/dev/null 2>&1; }

log() { echo "[tool_health] $*" >&2; }

if ! have_cmd jq; then
  log "jq not found; writing minimal ToolCaps."
  cat >"$OUT_ENV" <<'ENV'
export CLAUDE_TOOLCAPS="bash_exec,fs_rw"
ENV
  cat >"$OUT_JSON" <<'JSON'
{ "status": "degraded", "reason": "jq missing", "cli_tools": [], "mcp_servers": [], "models": [] }
JSON
  exit 0
fi

if [ ! -f "$MANIFEST" ]; then
  log "manifest not found: $MANIFEST"
  cat >"$OUT_ENV" <<'ENV'
export CLAUDE_TOOLCAPS="bash_exec,fs_rw"
ENV
  cat >"$OUT_JSON" <<'JSON'
{ "status": "degraded", "reason": "manifest missing", "cli_tools": [], "mcp_servers": [], "models": [] }
JSON
  exit 0
fi

# Read manifest values via jq
mapfile -t CLI_IDS < <(jq -r '.cli_tools[].id' "$MANIFEST")

# For version extraction
extract_version() {
  local text="$1" pattern="$2"
  # Use grep -Eo to extract first match
  echo "$text" | grep -Eo "$pattern" | head -n1 | sed -E 's/^v//'
}

RESULTS_JSON='{"cli_tools":[],"mcp_servers":[],"models":[]}'

TOOLCAPS=("bash_exec" "fs_rw")

# Evaluate each CLI tool
cli_len=$(jq -r '.cli_tools | length' "$MANIFEST")
for ((i=0; i<cli_len; i++)); do
  item=$(jq -r ".cli_tools[$i]" "$MANIFEST")
  id=$(jq -r '.id' <<<"$item")
  minv=$(jq -r '.min_version // ""' <<<"$item")
  verpat=$(jq -r '.version_pattern // "([0-9]+\\.[0-9]+\\.[0-9]+|[0-9]+)"' <<<"$item")
  capcsv=$(jq -r '.capabilities | join(",")' <<<"$item")

  # Try verify commands until one works
  ok=false
  version=""
  # Read array of verify commands
  readarray -t verifies < <(jq -r '.verify[]' <<<"$item")
  for cmd in "${verifies[@]}"; do
    # Extract the program name (first token) to check availability when possible
    prog="${cmd%% *}"
    if [[ "$cmd" == *"npx"* ]] || have_cmd "$prog"; then
      if out=$(bash -lc "$cmd" 2>/dev/null); then
        version=$(extract_version "$out" "$verpat")
        ok=true
        break
      fi
    fi
  done

  # Record in results
  caps_json=$(jq -Rc 'split(",")' <<<"$capcsv")
  RESULTS_JSON=$(jq \
    --arg id "$id" --arg ok "$ok" --arg version "$version" --arg minv "$minv" \
    --argjson caps "$caps_json" \
    '.cli_tools += [{id: $id, ok: ($ok=="true"), version: $version, min_version: $minv, capabilities: $caps}]' \
    <<<"$RESULTS_JSON")

  # Add to ToolCaps summary if detected
  if [ "$ok" = true ] && [ -n "$version" ]; then
    case "$id" in
      fd)
        TOOLCAPS+=("fd:$version")
        ;;
      *)
        TOOLCAPS+=("$id:$version")
        ;;
    esac
  elif [ "$ok" = true ]; then
    TOOLCAPS+=("$id")
  fi
done

# MCP servers: simply include declared capabilities for now
mcp_len=$(jq -r '.mcp_servers | length' "$MANIFEST")
for ((i=0; i<mcp_len; i++)); do
  m=$(jq -r ".mcp_servers[$i]" "$MANIFEST")
  mid=$(jq -r '.id' <<<"$m")
  caps=$(jq -r '.capabilities' <<<"$m")
  RESULTS_JSON=$(jq --arg id "$mid" --argjson caps "$caps" '.mcp_servers += [{id:$id, capabilities:$caps}]' <<<"$RESULTS_JSON")
done

# Models
ollama_ok=false
if have_cmd ollama; then ollama_ok=true; fi
gemini_ok=false
if [ -n "${GEMINI_API_KEY:-}" ]; then gemini_ok=true; fi

# Determine Ollama profile label
ollama_profile=$(jq -r '.models[] | select(.id=="ollama").default_profile' "$MANIFEST")
if [ -n "${OLLAMA_PROFILE:-}" ]; then ollama_profile="$OLLAMA_PROFILE"; fi

RESULTS_JSON=$(jq \
  --arg ollama_profile "$ollama_profile" \
  --argjson ollama_ok "$ollama_ok" \
  --argjson gemini_ok "$gemini_ok" \
  '.models += [{id:"ollama", ok:$ollama_ok, profile:$ollama_profile}, {id:"gemini", ok:$gemini_ok}]' \
  <<<"$RESULTS_JSON")

if [ "$ollama_ok" = true ]; then
  TOOLCAPS+=("ollama:$ollama_profile")
fi
if [ "$gemini_ok" = true ]; then
  TOOLCAPS+=("gemini:on")
else
  TOOLCAPS+=("gemini:off")
fi

# Write outputs
echo "$RESULTS_JSON" | jq '{status:"ok", detected:.}' >"$OUT_JSON"

cap_line=$(IFS=, ; echo "${TOOLCAPS[*]}")
cat >"$OUT_ENV" <<ENV
export CLAUDE_TOOLCAPS="$cap_line"
ENV

log "wrote $OUT_ENV with: $cap_line"
log "wrote $OUT_JSON"

