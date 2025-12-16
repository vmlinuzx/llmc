#!/usr/bin/env bash
# ==============================================================================
# Rem - Gap Analysis Demon (Gemini)
# ==============================================================================
# 
# The Void Gazer - finds missing tests and spawns workers to fill gaps.
#
# Usage:
#   ./thunderdome/agents/demons/rem_gap.sh --repo /path/to/repo
#   ./thunderdome/agents/demons/rem_gap.sh --repo /path/to/repo "Analyze auth module"
#
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THUNDERDOME_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$THUNDERDOME_ROOT/lib/common.sh"

DEMON_NAME="rem"
DEMON_SCOPE="gap"
PROMPT_FILE="$THUNDERDOME_ROOT/prompts/rem_gap.md"

: "${GEMINI_MODEL:=gemini-2.5-pro}"

# ==============================================================================
# Argument Parsing
# ==============================================================================

TARGET_REPO=""
USER_PROMPT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --repo)
            shift
            TARGET_REPO="${1:-}"
            ;;
        --help|-h)
            echo "Usage: $(basename "$0") --repo <path> [prompt]"
            exit 0
            ;;
        *)
            if [[ -z "$USER_PROMPT" ]]; then
                USER_PROMPT="$1"
            else
                USER_PROMPT="$USER_PROMPT $1"
            fi
            ;;
    esac
    shift
done

TARGET_REPO=$(resolve_target_repo "$TARGET_REPO")

if [[ ! -d "$TARGET_REPO" ]]; then
    err "Target repository does not exist: $TARGET_REPO"
    exit 1
fi

if ! have_cmd gemini; then
    err "Gemini CLI not found. Please ensure 'gemini' is in your PATH."
    exit 1
fi

# ==============================================================================
# Setup
# ==============================================================================

# Ensure gap analysis directories exist
mkdir -p "$TARGET_REPO/tests/gap/SDDs"
mkdir -p "$TARGET_REPO/tests/gap/REPORTS"

# ==============================================================================
# Build Prompt
# ==============================================================================

build_full_prompt() {
    if [[ -f "$PROMPT_FILE" ]]; then
        cat "$PROMPT_FILE"
    else
        err "Warning: Prompt file not found: $PROMPT_FILE"
        echo "You are a gap analysis agent. Find missing tests."
    fi
    
    echo ""
    echo "---"
    echo ""
    echo "## Context"
    echo ""
    repo_snapshot "$TARGET_REPO"
    echo ""
    
    echo ""
    echo "## Task"
    echo ""
    if [[ -n "$USER_PROMPT" ]]; then
        echo "$USER_PROMPT"
    else
        echo "Perform a gap analysis of this repository."
        echo "Look for: missing tests, untested error paths, security blind spots."
        echo "Create SDDs for each gap and spawn workers to implement tests."
    fi
}

# ==============================================================================
# Main
# ==============================================================================

log_header "Rem - Gap Analysis Demon"
log_info "Target: $TARGET_REPO"
log_info "Model: $GEMINI_MODEL"

init_report_dirs "$TARGET_REPO"

FULL_PROMPT=$(build_full_prompt)

cd "$TARGET_REPO"

log_info "Summoning Rem (Gap Analysis Mode)..."
echo ""

gemini -y -m "$GEMINI_MODEL" -p "$FULL_PROMPT"

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    log_success "Gap analysis completed"
else
    log_error "Gap analysis encountered issues (exit code: $EXIT_CODE)"
fi

exit $EXIT_CODE
