#!/usr/bin/env bash
# test_llm_gateway.sh - Test the LLM gateway

echo "Testing LLM Gateway..."
echo ""

# Test 1: Simple prompt via pipe
echo "Test 1: Echo prompt via pipe"
echo "What is 2+2? Answer in one word." | ./scripts/llm_gateway.sh
echo ""

# Test 2: Command line arg
echo "Test 2: Command line argument"
./scripts/llm_gateway.sh "What is the capital of France? Answer in one word."
echo ""

# Test 3: Force API
echo "Test 3: Force API with --api flag"
./scripts/llm_gateway.sh --api "What is 10*10? Answer in one word."
echo ""

echo "✅ All tests complete!"