#!/usr/bin/env bash
# ==============================================================================
# Rem - Security Audit Demon (Gemini)
# ==============================================================================
# 
# The Penetration Testing Demon - security-focused ruthless auditing.
#
# Usage:
#   ./thunderdome/agents/demons/rem_security.sh --repo /path/to/repo
#   ./thunderdome/agents/demons/rem_security.sh --repo /path/to/repo "Audit the MCP server"
#
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THUNDERDOME_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

source "$THUNDERDOME_ROOT/lib/common.sh"

DEMON_NAME="rem"
DEMON_SCOPE="security"
PROMPT_FILE="$THUNDERDOME_ROOT/prompts/rem_security.md"

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

# Ensure security test directories exist
mkdir -p "$TARGET_REPO/tests/security/REPORTS"
mkdir -p "$TARGET_REPO/tests/security/exploits"

# ==============================================================================
# Build Prompt
# ==============================================================================

build_full_prompt() {
    if [[ -f "$PROMPT_FILE" ]]; then
        cat "$PROMPT_FILE"
    else
        err "Warning: Prompt file not found: $PROMPT_FILE"
        echo "You are a ruthless security testing agent. Find vulnerabilities."
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
        echo "Perform a comprehensive security audit of this repository."
        echo "Focus on: command injection, path traversal, secrets in code, unsafe deserialization."
        echo "Check recent commits for security regressions."
    fi
}

# ==============================================================================
# Main
# ==============================================================================

log_header "Rem - Security Demon"
log_info "Target: $TARGET_REPO"
log_info "Model: $GEMINI_MODEL"

init_report_dirs "$TARGET_REPO"

FULL_PROMPT=$(build_full_prompt)

cd "$TARGET_REPO"

log_info "Summoning Rem (Security Mode)..."
echo ""

gemini -y -m "$GEMINI_MODEL" -p "$FULL_PROMPT"

EXIT_CODE=$?

if [[ $EXIT_CODE -eq 0 ]]; then
    log_success "Security audit completed"
else
    log_error "Security audit encountered issues (exit code: $EXIT_CODE)"
fi

exit $EXIT_CODE
