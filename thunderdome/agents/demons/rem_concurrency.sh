#!/usr/bin/env bash
# Rem - Concurrency Demon (Gemini)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THUNDERDOME_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$THUNDERDOME_ROOT/lib/common.sh"

: "${GEMINI_MODEL:=gemini-2.5-pro}"
TARGET_REPO="" USER_PROMPT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --repo) shift; TARGET_REPO="${1:-}" ;;
        *) USER_PROMPT="${USER_PROMPT:+$USER_PROMPT }$1" ;;
    esac
    shift
done

TARGET_REPO=$(resolve_target_repo "$TARGET_REPO")
[[ ! -d "$TARGET_REPO" ]] && { err "Repo not found: $TARGET_REPO"; exit 1; }
have_cmd gemini || { err "gemini CLI not found"; exit 1; }

log_header "Rem - Concurrency Demon"
log_info "Target: $TARGET_REPO"
init_report_dirs "$TARGET_REPO"
cd "$TARGET_REPO"

PROMPT="You are Rem the Concurrency Testing Demon.
Focus area: concurrency testing and analysis.
Write report to ./tests/REPORTS/current/rem_concurrency_$(date +%Y-%m-%d).md

Context:
$(repo_snapshot "$TARGET_REPO")

Task: ${USER_PROMPT:-Perform concurrency analysis on this repository.}"

gemini -y -m "$GEMINI_MODEL" -p "$PROMPT"
