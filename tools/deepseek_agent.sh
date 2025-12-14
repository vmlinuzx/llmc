#!/bin/bash
# DeepSeek Agent Wrapper for Thunderdome
# Usage: ./deepseek_agent.sh "Your prompt here"
# Requires: DEEPSEEK_API_KEY environment variable

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
    echo "ERROR: DEEPSEEK_API_KEY environment variable not set" >&2
    exit 1
fi

MODEL="deepseek-chat"

# Escape the prompt for JSON
PROMPT="$1"
ESCAPED_PROMPT=$(echo "$PROMPT" | jq -Rs '.')

# Make the API call
RESPONSE=$(curl -s https://api.deepseek.com/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -d "{
    \"model\": \"$MODEL\",
    \"messages\": [
      {\"role\": \"system\", \"content\": \"You are a senior software engineer. You write clean, tested code. You follow instructions precisely.\"},
      {\"role\": \"user\", \"content\": $ESCAPED_PROMPT}
    ],
    \"stream\": false,
    \"max_tokens\": 8192
  }")

# Extract the response content
echo "$RESPONSE" | jq -r '.choices[0].message.content'
