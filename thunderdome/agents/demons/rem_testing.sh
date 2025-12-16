#!/usr/bin/env bash
# ==============================================================================
# Rem - Ruthless Testing Demon (Gemini)
# ==============================================================================
# 
# The Maiden Warrior Bug Hunting Demon - ruthless test runner using Gemini.
#
# Usage:
#   ./thunderdome/agents/demons/rem_testing.sh --repo /path/to/repo
#   ./thunderdome/agents/demons/rem_testing.sh --repo /path/to/repo "Test the MCP tools"
#
# Environment:
#   GEMINI_API_KEY     - Required: Gemini API key
#   GEMINI_MODEL       - Optional: Model to use (default: gemini-2.5-pro)
#
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THUNDERDOME_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source common library
source "$THUNDERDOME_ROOT/lib/common.sh"

# ==============================================================================
# Configuration
# ==============================================================================

DEMON_NAME="rem"
DEMON_SCOPE="testing"
PROMPT_FILE="$THUNDERDOME_ROOT/prompts/rem_testing.md"

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
            echo ""
            echo "Options:"
            echo "  --repo <path>   Target repository to test (required)"
            echo "  [prompt]        Optional specific testing instructions"
            exit 0
            ;;
        *)
            # Collect remaining args as user prompt
            if [[ -z "$USER_PROMPT" ]]; then
                USER_PROMPT="$1"
            else
                USER_PROMPT="$USER_PROMPT $1"
            fi
            ;;
    esac
    shift
done

# Resolve target repo
TARGET_REPO=$(resolve_target_repo "$TARGET_REPO")

if [[ ! -d "$TARGET_REPO" ]]; then
    err "Target repository does not exist: $TARGET_REPO"
    exit 1
fi

# Verify gemini CLI exists
if ! have_cmd gemini; then
    err "Gemini CLI not found. Please ensure 'gemini' is in your PATH."
    exit 1
fi

# ==============================================================================
# Build Prompt
# ==============================================================================

build_full_prompt() {
    # Read the canonical prompt
    if [[ -f "$PROMPT_FILE" ]]; then
        cat "$PROMPT_FILE"
    else
        err "Warning: Prompt file not found: $PROMPT_FILE"
        echo "You are a ruthless testing agent. Find bugs."
    fi
    
    echo ""
    echo "---"
    echo ""
    echo "## Context"
    echo ""
    repo_snapshot "$TARGET_REPO"
    echo ""
    
    # Add user request
    echo ""
    echo "## Task"
    echo ""
    if [[ -n "$USER_PROMPT" ]]; then
        echo "$USER_PROMPT"
    else
        echo "Perform ruthless testing of recent changes in this repository."
        echo "Focus on functional correctness, performance, edge cases, and code quality."
        echo "Review the latest commits and test anything new or modified."
    fi
}

# ==============================================================================
# Main
# ==============================================================================

log_header "Rem - Testing Demon"
log_info "Target: $TARGET_REPO"
log_info "Model: $GEMINI_MODEL"

# Ensure report directories exist
init_report_dirs "$TARGET_REPO"

# Build the prompt
FULL_PROMPT=$(build_full_prompt)

# Change to target repo
cd "$TARGET_REPO"

# Execute Gemini with the prompt
log_info "Summoning Rem..."
echo ""

# Run gemini in autonomous mode (-y skips confirmation)
gemini -y -m "$GEMINI_MODEL" -p "$FULL_PROMPT"

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    log_success "Rem completed testing"
else
    log_error "Rem encountered issues (exit code: $EXIT_CODE)"
fi

exit $EXIT_CODE
