#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# THUNDERDOME DISPATCH
# Send commands to the agent pane from the orchestrator
# ═══════════════════════════════════════════════════════════════════

SESSION_NAME="thunderdome"

usage() {
    echo "Usage: $0 <command>"
    echo "       $0 agent <command>"
    echo ""
    echo "Dispatches command to the AGENT pane."
    echo ""
    echo "Examples:"
    echo "  $0 'gemini -y \"Fix the bug\"'           # Run gemini agent"
    echo "  $0 'pytest tests/ -v'                  # Run tests"
    echo "  $0 agent 'gemini -y \"Fix the bug\"'   # Run gemini"
    echo ""
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
fi

# Handle optional 'agent' prefix
if [[ "$1" == "agent" ]]; then
    shift
fi

COMMAND="$*"

if [[ -z "$COMMAND" ]]; then
    usage
fi

# Check if session exists
if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Error: Thunderdome session not running."
    echo "Start it with: ./tools/thunderdome-session.sh"
    exit 1
fi

# Send to the agent pane (pane 2)
echo "Dispatching to AGENT pane: $COMMAND"
tmux send-keys -t "$SESSION_NAME:0.2" "$COMMAND" Enter

# Log the dispatch
WORKDIR=$(tmux display-message -t "$SESSION_NAME" -p '#{pane_current_path}' 2>/dev/null || echo ".")
echo "{\"ts\":\"$(date -Iseconds)\",\"agent\":\"dispatch\",\"command\":\"$COMMAND\"}" >> "$WORKDIR/turn_log.jsonl" 2>/dev/null || true
