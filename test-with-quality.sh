#!/bin/bash
# Final verification test

echo "🧪 Final Service Test with Quality Check"
echo "=========================================="
echo ""

cd /home/vmlinux/src/llmc

# Set environment
export ENRICH_BACKEND=ollama
export ENRICH_ROUTER=on
export ENRICH_START_TIER=7b
export ENRICH_BATCH_SIZE=1
export ENRICH_MAX_SPANS=5
export ENRICH_QUALITY_CHECK=on

echo "✅ Environment configured"
echo "✅ Quality check enabled"
echo ""
echo "Starting one service cycle..."
echo "(Press Ctrl+C after it completes)"
echo ""

python3 scripts/llmc-rag-service start --interval 300
