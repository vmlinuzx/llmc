#!/bin/bash
# Test Azure OpenAI connection with the llmc project

cd /home/vmlinux/src/llmc

# Source the .env.local file
set -a
source .env.local
set +a

# Enable LLM for testing
export LLM_DISABLED=0
export NEXT_PUBLIC_LLM_DISABLED=0
export WEATHER_DISABLED=0

echo "Testing Azure OpenAI configuration:"
echo "Endpoint: $AZURE_OPENAI_ENDPOINT"
echo "Deployment: $AZURE_OPENAI_DEPLOYMENT"
echo "API Version: $AZURE_OPENAI_API_VERSION"
echo ""

node scripts/llm_gateway.js --api --debug "Say hello in one sentence"
