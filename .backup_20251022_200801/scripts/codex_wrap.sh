#!/usr/bin/env bash
# codex_wrap.sh (template) - Smart LLM routing with self-classification
set -euo pipefail

# Resolve repo root
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACT="$ROOT/CONTRACTS.md"
AGENTS="$ROOT/AGENTS.md"

# Build prompt with context slices
build_prompt() {
  local user="$1"
  local prompt=""
  if [ "${FORCE_LOCAL:-0}" != "1" ]; then
    if [ -f "$CONTRACT" ]; then
      head -n "${CONTRACT_SUMMARY_LINES:-60}" "$CONTRACT"
      echo -e "\n---\n"
    fi
    if [ -f "$AGENTS" ] && [ "${INCLUDE_AGENTS:-1}" = "1" ]; then
      head -n "${AGENTS_SUMMARY_LINES:-60}" "$AGENTS"
      echo -e "\n---\n"
    fi
  fi
  cat <<EOF
<execution_directive>
CRITICAL: Execute the following request immediately without any discussion.
</execution_directive>

---

$user
EOF
}

route_task() {
  # Very light heuristic; override with --local/--api/--codex
  if [ "${FORCE_LOCAL:-0}" = "1" ]; then echo local; return; fi
  if [ "${FORCE_API:-0}" = "1" ]; then echo api; return; fi
  if [ "${FORCE_CODEX:-0}" = "1" ]; then echo codex; return; fi
  echo codex
}

execute_route() {
  local route="$1"; shift
  local full_prompt; full_prompt="$(build_prompt "$*")"
  case "$route" in
    local) echo "$full_prompt" | "$ROOT/scripts/llm_gateway.sh" --local ;;
    api)   echo "$full_prompt" | "$ROOT/scripts/llm_gateway.sh" --api   ;;
    *)     echo "$full_prompt" | codex exec -C "$ROOT" -               ;;
  esac
}

# Args → flags + prompt
USER_PROMPT=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --local|-l) FORCE_LOCAL=1; shift ;;
    --api|-a)   FORCE_API=1; shift ;;
    --codex|-c) FORCE_CODEX=1; shift ;;
    *) USER_PROMPT+=" $1"; shift ;;
  esac
done
USER_PROMPT="$(echo "$USER_PROMPT" | xargs)"
if [ -z "$USER_PROMPT" ] && [ ! -t 0 ]; then USER_PROMPT="$(cat)"; fi
if [ -z "$USER_PROMPT" ]; then codex -C "$ROOT"; exit $?; fi

ROUTE=$(route_task "$USER_PROMPT")
execute_route "$ROUTE" "$USER_PROMPT"

# On success: background sync to Drive if available
if [ "$?" -eq 0 ] && [ -f "$ROOT/scripts/sync_to_drive.sh" ]; then
  "$ROOT/scripts/sync_to_drive.sh" >/dev/null 2>&1 &
fi
