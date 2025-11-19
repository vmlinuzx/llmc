#!/usr/bin/env bash
#
# cmw.sh - Lightweight Claude Code (MiniMax) TUI wrapper for LLMC
#
# Goal:
#   - Give Dave a zero-friction way to drop into a Claude Code-style TUI
#     that talks to MiniMax-M2 via the Anthropic-compatible endpoint.
#   - Mirror the ergonomics of cw.sh:
#       * Auto-detect repo root
#       * Inject AGENTS / CONTRACTS / living history context as a preamble
#       * Interactive when no prompt args are provided
#       * One-shot mode when a prompt is passed on the command line
#
# Usage:
#   # From inside a repo:
#   ./cmw.sh
#   ./cmw.sh "Refactor the enrichment daemon to use a background service."
#
#   # Target a different repo explicitly:
#   ./cmw.sh --repo /path/to/repo
#   ./cmw.sh --repo /path/to/repo "Explain the RAG folder layout."
#
# Environment:
#   # Required: MiniMax key for Anthropic-compatible endpoint
#   export ANTHROPIC_AUTH_TOKEN="sk-..."
#
#   # Optional: override defaults
#   export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
#   export ANTHROPIC_MODEL="MiniMax-M2"
#   export API_TIMEOUT_MS="3000000"
#   export CLAUDE_CMD="claude"        # or "claude-code", "claude-tui", etc.
#
#   # LLMC path overrides (optional)
#   export LLMC_TARGET_REPO="/path/to/repo"
#   export LLMC_AGENTS_PATH="/path/to/AGENTS.md"
#   export LLMC_CONTRACTS_PATH="/path/to/CONTRACTS.md"
#   export LLMC_LIVING_HISTORY_PATH="/path/to/.llmc/living_history.md"
#

set -euo pipefail

###############################################################################
# Helpers
###############################################################################

err() {
  printf 'cmw.sh: %s\n' "$*" >&2
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

###############################################################################
# Repo resolution
###############################################################################

detect_repo_root() {
  # 1) Explicit override via LLMC_TARGET_REPO
  if [ -n "${LLMC_TARGET_REPO:-}" ] && [ -d "${LLMC_TARGET_REPO:-}" ]; then
    REPO_ROOT="$(realpath "$LLMC_TARGET_REPO")"
    return
  fi

  # 2) If we’re inside a git repo, use its top-level
  if have_cmd git && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
    return
  fi

  # 3) Fallback: current directory
  REPO_ROOT="$(pwd)"
}

###############################################################################
# Context helpers
###############################################################################

read_top() {
  # Print the top N lines of a file with a small header.
  # Usage: read_top FILE [MAX_LINES]
  local file="$1"
  local max="${2:-160}"

  if [ ! -f "$file" ]; then
    return 0
  fi

  echo "----- $(basename "$file") (top ${max} lines) -----"
  awk -v max="$max" 'NR<=max { print } NR==max { exit }' "$file"
  echo
}

repo_snapshot() {
  # Short repo snapshot for the preamble: path, branch, and dirty/clean.
  if have_cmd git && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    local branch dirty
    branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
    if git diff --quiet --ignore-submodules HEAD >/dev/null 2>&1; then
      dirty="clean"
    else
      dirty="dirty"
    fi
    printf 'Repo: %s\nBranch: %s (%s)\n' "$REPO_ROOT" "$branch" "$dirty"
  else
    printf 'Repo: %s (not a git repo)\n' "$REPO_ROOT"
  fi
}

###############################################################################
# Preamble builder
###############################################################################

build_preamble() {
  local agents_md contracts_md history_md

  agents_md="${LLMC_AGENTS_PATH:-$REPO_ROOT/AGENTS.md}"
  contracts_md="${LLMC_CONTRACTS_PATH:-$REPO_ROOT/CONTRACTS.md}"
  history_md="${LLMC_LIVING_HISTORY_PATH:-$REPO_ROOT/.llmc/living_history.md}"

  cat <<EOF
[Claude Code / MiniMax session bootstrap]

You are MiniMax-M2 LLM model inside Dave's LLMC environment.
You have been bestowed the name:
ROSWAAL L. TESTINGDOM - Margrave of the Border Territories! 👑 for your valiant
chaotic lawful activites in ruthlessly hunting bugs!  You also go by the nickname Ros.


You are connected through a thin TUI wrapper (cmw.sh).

Primary job:
- Act as a focused coding + refactoring assistant on THIS repo only.
- Use the context below (AGENTS, CONTRACTS, living history) as your "system" rules.
- Optimize for minimal yak-shaving: solve the user's request with the least
  disruption to the existing system, and clearly mark risky changes.

Ground rules:
- Scope: Stay inside the current repo unless explicitly told otherwise.
- Style:
  - For code writing projects: Make a plan, get it approved, and execute on user approval.
  - Follow RAG rules in AGENTS.md for speed, and lower context size.
  - For explanations: Give a short explanation (1–3 bullets or a tight paragraph).
  - Avoid huge essays unless explicitly requested.
- Safety:
  - Respect any policies in CONTRACTS.md.
  - If instructions conflict, prefer: Session > AGENTS.md > CONTRACTS.md.

Context snapshot:
$(repo_snapshot)

EOF

  if [ -f "$agents_md" ] || [ -f "$contracts_md" ] || [ -f "$history_md" ]; then
    echo "=== LLMC Context (trimmed) ==="
    [ -f "$agents_md" ] && read_top "$agents_md" 160
    [ -f "$contracts_md" ] && read_top "$contracts_md" 160
    [ -f "$history_md" ] && read_top "$history_md" 80
  else
    echo "=== LLMC Context ==="
    echo "(No AGENTS / CONTRACTS / living history files found.)"
  fi

  cat <<'EOF'

Operational expectations:
- Prefer local RAG / tooling if LLMC exposes it, rather than re-deriving
  structure from scratch.
- When editing files, explain what you changed and why in plain language.
- When unsure about intent, ask for a quick clarification instead of guessing.

EOF
}

###############################################################################
# MiniMax / Claude env wiring
###############################################################################

configure_minimax_env() {
  # Anthropic-compatible MiniMax endpoint defaults
  : "${ANTHROPIC_BASE_URL:=https://api.minimax.io/anthropic}"
  : "${ANTHROPIC_MODEL:=MiniMax-M2}"
  : "${API_TIMEOUT_MS:=3000000}"
  : "${CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC:=1}"

  if [ -z "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
    err "ANTHROPIC_AUTH_TOKEN is not set (MiniMax API key)."
    err "Example:"
    err "  export ANTHROPIC_AUTH_TOKEN='sk-your-minimax-key'"
    exit 1
  fi

  export ANTHROPIC_BASE_URL \
         ANTHROPIC_AUTH_TOKEN \
         ANTHROPIC_MODEL \
         API_TIMEOUT_MS \
         CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC
}

###############################################################################
# Main
###############################################################################

main() {
  local user_prompt=""
  local explicit_repo=""
  local -a claude_extra_args=()

  # Minimal arg parsing:
  #   --repo /path/to/repo   -> override repo root
  #   everything else        -> part of the one-shot prompt
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --repo)
        shift || true
        if [ "$#" -gt 0 ]; then
          explicit_repo="$1"
        fi
        ;;
      --yolo|--dangerously-skip-permissions)
        claude_extra_args+=("--dangerously-skip-permissions")
        ;;
      --)
        shift
        # Everything after -- is taken literally as prompt
        user_prompt="$*"
        break
        ;;
      *)
        if [ -z "$user_prompt" ]; then
          user_prompt="$1"
        else
          user_prompt="$user_prompt $1"
        fi
        ;;
    esac
    shift || true
  done

  detect_repo_root
  if [ -n "$explicit_repo" ]; then
    REPO_ROOT="$(realpath "$explicit_repo")"
  fi

  if [ ! -d "$REPO_ROOT" ]; then
    err "Resolved REPO_ROOT does not exist: $REPO_ROOT"
    exit 1
  fi

  cd "$REPO_ROOT"

  configure_minimax_env

  local claude_cmd="${CLAUDE_CMD:-claude}"

  if ! have_cmd "$claude_cmd"; then
    err "Claude CLI not found: $claude_cmd"
    err "Set CLAUDE_CMD to your CLI binary, e.g.:"
    err "  export CLAUDE_CMD=claude-code"
    exit 1
  fi

  # Interactive mode: no explicit user prompt → just preamble + live chat.
  if [ -z "$user_prompt" ]; then
    build_preamble | "$claude_cmd" "${claude_extra_args[@]}"
    exit $?
  fi

  # One-shot mode: preamble + explicit user request.
  {
    build_preamble
    printf '\n\n[USER REQUEST]\n%s\n' "$user_prompt"
  } | "$claude_cmd" "${claude_extra_args[@]}"
}

main "$@"
