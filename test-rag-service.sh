#!/bin/bash
# Quick test script to see if the fixed service works

echo "🧪 Testing fixed RAG service..."
echo ""
echo "This will run ONE cycle manually (not as daemon)"
echo "Press Ctrl+C after the first cycle completes"
echo ""

cd /home/vmlinux/src/llmc

# Set environment variables for enrichment
export ENRICH_BACKEND=ollama
export ENRICH_ROUTER=on
export ENRICH_START_TIER=7b
export ENRICH_BATCH_SIZE=2
export ENRICH_MAX_SPANS=5
export ENRICH_COOLDOWN=0
export ENRICH_EMBED_LIMIT=10

echo "Environment:"
echo "  ENRICH_BACKEND=$ENRICH_BACKEND"
echo "  ENRICH_ROUTER=$ENRICH_ROUTER"
echo "  ENRICH_START_TIER=$ENRICH_START_TIER"
echo "  ENRICH_BATCH_SIZE=$ENRICH_BATCH_SIZE"
echo "  ENRICH_MAX_SPANS=$ENRICH_MAX_SPANS"
echo ""
echo "Starting service (manual test)..."
echo ""

python3 scripts/llmc-rag-service start --interval 300
