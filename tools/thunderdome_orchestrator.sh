#!/usr/bin/env bash
# ==============================================================================
# THUNDERDOME ORCHESTRATOR AGENT
# ==============================================================================
#
# Wrapper that launches an agent with the Thunderdome protocol pre-loaded.
# Uses the same pattern as rem_ruthless_testing_agent.sh
#
# Usage:
#   ./tools/thunderdome_orchestrator.sh                    # Interactive mode
#   ./tools/thunderdome_orchestrator.sh "Execute Phase 1"  # One-shot prompt
#
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${LLMC_TARGET_REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PROTOCOL_FILE="/home/vmlinux/src/thunderdome/DIALECTICAL_AUTOCODING1.3.md"

# Model selection
MODEL="${THUNDERDOME_MODEL:-gemini-2.5-pro}"

# Colors
CYAN='\033[0;36m'
PURPLE='\033[0;35m'
NC='\033[0m'

# ==============================================================================
# Build the orchestrator preamble
# ==============================================================================

build_preamble() {
    cat <<'PREAMBLE'
[THUNDERDOME ORCHESTRATOR SESSION]

You are the ORCHESTRATOR for the Thunderdome dialectical autocoding system.

PREAMBLE

    # Include the protocol
    if [[ -f "$PROTOCOL_FILE" ]]; then
        echo "=== PROTOCOL (DIALECTICAL_AUTOCODING) ==="
        cat "$PROTOCOL_FILE"
        echo ""
        echo "=== END PROTOCOL ==="
    else
        echo "WARNING: Protocol file not found at $PROTOCOL_FILE"
    fi

    # Add repo context
    cat <<CONTEXT

=== CURRENT CONTEXT ===
Repository: $REPO_ROOT
Date: $(date -Iseconds)
Branch: $(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || echo "unknown")

You are running in a TMUX workspace with:
- ORCHESTRATOR pane (you)
- AGENT pane (dispatch agents here with ./tools/dispatch.sh)
- LOG pane (watching turn_log.jsonl)

Ready for target acquisition.
CONTEXT
}

# ==============================================================================
# Main
# ==============================================================================

main() {
    local user_prompt=""

    # Collect any user prompt from command line
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --model)
                MODEL="$2"
                shift 2
                ;;
            *)
                if [[ -z "$user_prompt" ]]; then
                    user_prompt="$1"
                else
                    user_prompt="$user_prompt $1"
                fi
                shift
                ;;
        esac
    done

    cd "$REPO_ROOT"

    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║           THUNDERDOME ORCHESTRATOR                           ║"
    echo "║           Model: $MODEL                                      ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"

    echo -e "${CYAN}Launching agent...${NC}"
    echo ""

    # Create the initial message
    local init_msg="You are the THUNDERDOME ORCHESTRATOR. Read and internalize the protocol at /home/vmlinux/src/thunderdome/DIALECTICAL_AUTOCODING1.3.md - this defines your role and behavior. After reading, display the Phase 0 greeting and ask for the SDD path."
    
    # Add user request if provided
    if [[ -n "$user_prompt" ]]; then
        init_msg="$init_msg Then: $user_prompt"
    fi

    # Save message to temp file for send-keys
    echo "$init_msg" > /tmp/thunderdome_init_msg.txt

    # Launch gemini with context
    gemini -y "$init_msg"
}

main "$@"
