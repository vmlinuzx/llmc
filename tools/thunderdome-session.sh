#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# THUNDERDOME SESSION LAUNCHER
# Creates a tmux workspace for dialectical autocoding
# ═══════════════════════════════════════════════════════════════════

SESSION_NAME="thunderdome"
WORKDIR="${1:-$(pwd)}"
PROTOCOL_FILE="/home/vmlinux/src/thunderdome/DIALECTICAL_AUTOCODING1.3.md"

# Kill existing session if it exists
tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true

# Create new session
tmux new-session -d -s "$SESSION_NAME" -c "$WORKDIR" -n main

# ═══════════════════════════════════════════════════════════════════
# ENABLE MOUSE MODE
# ═══════════════════════════════════════════════════════════════════
tmux set -g mouse on

# ═══════════════════════════════════════════════════════════════════
# CREATE LAYOUT
# ═══════════════════════════════════════════════════════════════════
#
# ┌───────────────────┬───────────────────────────────┐
# │                   │                               │
# │   ORCHESTRATOR    │                               │
# │      (pane 0)     │        ACTIVE AGENT           │
# │                   │          (pane 2)             │
# ├───────────────────┤                               │
# │                   │   Spawned by orchestrator:    │
# │       LOG         │   ./tools/dispatch.sh agent   │
# │     (pane 1)      │                               │
# │                   │                               │
# └───────────────────┴───────────────────────────────┘

# Split horizontal: left (orchestrator) | right (agent)
tmux split-window -h -t "$SESSION_NAME:0"

# Split left pane vertical: orchestrator (top) | log (bottom)
tmux split-window -v -t "$SESSION_NAME:0.0"

# ═══════════════════════════════════════════════════════════════════
# RESIZE PANES (adjust these values as needed)
# ═══════════════════════════════════════════════════════════════════
LEFT_WIDTH=50   # Percentage for left column (orchestrator + log)
LOG_HEIGHT=30   # Percentage for log pane (within left column)

# Set left column width
tmux resize-pane -t "$SESSION_NAME:0.0" -x "${LEFT_WIDTH}%"
# Set log pane height  
tmux resize-pane -t "$SESSION_NAME:0.1" -y "${LOG_HEIGHT}%"

# Set pane titles
tmux select-pane -t "$SESSION_NAME:0.0" -T "ORCHESTRATOR"
tmux select-pane -t "$SESSION_NAME:0.1" -T "LOG"
tmux select-pane -t "$SESSION_NAME:0.2" -T "AGENT"

# Enable pane titles display
tmux set -t "$SESSION_NAME" pane-border-status top
tmux set -t "$SESSION_NAME" pane-border-format " #{pane_title} "
tmux set -t "$SESSION_NAME" pane-active-border-style "fg=cyan"

# ═══════════════════════════════════════════════════════════════════
# INITIALIZE PANES
# ═══════════════════════════════════════════════════════════════════

# LOG pane - tail the turn log
touch "$WORKDIR/turn_log.jsonl" 2>/dev/null || true
tmux send-keys -t "$SESSION_NAME:0.1" "tail -f turn_log.jsonl" Enter

# AGENT pane - ready to receive commands
tmux send-keys -t "$SESSION_NAME:0.2" "# AGENT PANE - Orchestrator will spawn agents here" Enter
tmux send-keys -t "$SESSION_NAME:0.2" "# Or manually run: gemini -y 'prompt'" Enter

# ORCHESTRATOR pane - start orchestrator with protocol
tmux send-keys -t "$SESSION_NAME:0.0" "./tools/thunderdome_orchestrator.sh" Enter

# Wait for agent to start, then inject the initial message
sleep 3
if [[ -f /tmp/thunderdome_init_msg.txt ]]; then
    tmux send-keys -t "$SESSION_NAME:0.0" "$(cat /tmp/thunderdome_init_msg.txt)" Enter
fi

# Focus orchestrator
tmux select-pane -t "$SESSION_NAME:0.0"

echo "═══════════════════════════════════════════════════════════════════"
echo "  THUNDERDOME SESSION CREATED"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "  Layout: ORCHESTRATOR + LOG (left) | AGENT (right)"
echo "  Mouse mode: ENABLED"
echo ""
echo "  Dispatch agents with:"
echo "    ./tools/dispatch.sh agent 'gemini -y prompt'"
echo "    ./tools/dispatch.sh agent 'pytest tests/'"
echo ""
echo "  Attaching..."
echo "═══════════════════════════════════════════════════════════════════"

# Attach to the session
tmux attach -t "$SESSION_NAME"
