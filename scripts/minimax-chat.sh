#!/usr/bin/env bash
# minimax-chat.sh - Quick REPL for MiniMax using native API
set -euo pipefail

MINIMAX_TOKEN="${MINIMAX_API_KEY:-}"
if [ -z "$MINIMAX_TOKEN" ]; then
  echo "Error: Set MINIMAX_API_KEY environment variable"
  exit 1
fi

CONVERSATION=()

chat() {
  local user_input="$1"
  
  # Build messages JSON array
  local messages="["
  for ((i=0; i<${#CONVERSATION[@]}; i+=2)); do
    messages+="{\"role\":\"user\",\"content\":\"${CONVERSATION[i]}\"},"
    if [ $((i+1)) -lt ${#CONVERSATION[@]} ]; then
      messages+="{\"role\":\"assistant\",\"content\":\"${CONVERSATION[i+1]}\"},"
    fi
  done
  messages+="{\"role\":\"user\",\"content\":\"$user_input\"}]"
  
  # Call MiniMax
  local response=$(curl -s -X POST "https://api.minimax.io/v1/text/chatcompletion_v2" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $MINIMAX_TOKEN" \
    -d "{\"model\":\"minimax-m2\",\"messages\":$messages}" \
    --max-time 30)
  
  # Extract assistant reply
  local reply=$(echo "$response" | jq -r '.choices[0].message.content // "Error: No response"')
  
  # Store in conversation
  CONVERSATION+=("$user_input")
  CONVERSATION+=("$reply")
  
  echo "$reply"
}

echo "🤖 MiniMax Chat (Ctrl+C to exit)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

while true; do
  echo ""
  read -p "You: " input
  [ -z "$input" ] && continue
  
  echo ""
  echo "MiniMax: $(chat "$input")"
done
