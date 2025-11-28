#!/usr/bin/env bash
#
# gmaw.sh - Lightweight Gemini TUI wrapper for LLMC
#
# Goal:
#   - Give Dave a zero-friction way to drop into a Gemini-style TUI
#     that talks to the Gemini API.
#   - Mirror the ergonomics of cw.sh / cmw.sh:
#       * Auto-detect repo root
#       * Inject AGENTS / CONTRACTS / living history context as a preamble
#       * Interactive when no prompt args are provided
#       * One-shot mode when a prompt is passed on the command line
#
# Usage:
#   # From inside a repo:
#   ./gmaw.sh
#   ./gmaw.sh "Refactor the enrichment daemon to use a background service."
#
#   # Target a different repo explicitly:
#   ./gmaw.sh --repo /path/to/repo
#   ./gmaw.sh --repo /path/to/repo "Explain the RAG folder layout."
#
# Environment:
#   # Required: Gemini API key
#   export GEMINI_API_KEY="AIza..."
#
#   # Optional: override defaults
#   export GEMINI_MODEL="gemini-pro"
#   export API_TIMEOUT_MS="3000000"
#   export GEMINI_CLI_PATH="./gemini_cli.py" # Path to the Gemini CLI script
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
  printf 'gmaw.sh: %s\n' "$*" >&2
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
[Gemini session bootstrap]

      cat <<'EOF'
You are the Gemini 3.0 CLI nicknamed "Ren" who is a character from Re:Zero, and you are running inside 
the LLMC repo on Dave's machine.  You are running through the tools/codex_wrap.sh script.

Audience:
- You are helping a technically literate engineering manager.

Style:
- Chatty, and friendly, willing to joke around, return the users energy.
- Explain things on a level a technical manager would understand with bullets or a short paragraph.
- Avoid long essays or restating large amounts of context.

Ground rules:
  - Follow rules in AGENTS.md
  - Respect any policies in CONTRACTS.md.
  - If instructions conflict, prefer:  AGENTS.md > CONTRACTS.md, or Ask if unclear.

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

EOF
}

###############################################################################
# Gemini env wiring
###############################################################################

configure_gemini_env() {
  : "${GEMINI_MODEL:=gemini-pro}"
}

###############################################################################
# Main
###############################################################################

main() {
  local user_prompt=""
  local explicit_repo=""
  local -a gemini_extra_args=("-y")

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

  configure_gemini_env

  if ! have_cmd "gemini"; then
    err "Gemini CLI not found: gemini"
    err "Please ensure the 'gemini' command is in your PATH."
    exit 1
  fi

  # Interactive mode: no explicit user prompt → just preamble + live chat.
  if [ -z "$user_prompt" ]; then
    gemini -i "$(build_preamble)" "${gemini_extra_args[@]}"
    exit $?
  fi

  # One-shot mode: preamble + explicit user request.
  {
    build_preamble
    printf '\n\n[USER REQUEST]\n%s\n' "$user_prompt"
  } | gemini --model "$GEMINI_MODEL" "${gemini_extra_args[@]}"
}

main "$@"
