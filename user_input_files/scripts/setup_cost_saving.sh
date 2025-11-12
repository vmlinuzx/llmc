#!/usr/bin/env bash
# setup_cost_saving.sh - Quick setup for maximum cost savings with claude_wrap.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env.local"

echo "💰 Claude Wrap Cost-Saving Setup"
echo "================================="
echo ""

# Check if .env.local exists
if [ -f "$ENV_FILE" ]; then
    echo "✓ Found existing .env.local"
else
    echo "⚠️  No .env.local found. Copying from example..."
    if [ -f "$ROOT/.env.local.example" ]; then
        cp "$ROOT/.env.local.example" "$ENV_FILE"
        echo "✓ Created .env.local from example"
    else
        echo "❌ No .env.local.example found. Creating basic .env.local..."
        cat > "$ENV_FILE" <<EOF
# LLMC Environment Configuration
LLM_DISABLED=false
SEMANTIC_CACHE_ENABLE=1
EOF
    fi
fi

echo ""
echo "🔧 Configuring cost-saving features..."
echo ""

# Function to update or add a setting
update_setting() {
    local key="$1"
    local value="$2"
    local file="$ENV_FILE"

    if grep -q "^${key}=" "$file" 2>/dev/null; then
        # Setting exists, update it
        sed -i.bak "s|^${key}=.*|${key}=${value}|" "$file"
        echo "  ✓ Updated: ${key}=${value}"
    elif grep -q "^# ${key}=" "$file" 2>/dev/null; then
        # Setting is commented, uncomment and update
        sed -i.bak "s|^# ${key}=.*|${key}=${value}|" "$file"
        echo "  ✓ Enabled: ${key}=${value}"
    else
        # Setting doesn't exist, add it
        echo "${key}=${value}" >> "$file"
        echo "  ✓ Added: ${key}=${value}"
    fi
}

# 1. Enable LLM features
update_setting "LLM_DISABLED" "false"

# 2. Enable semantic caching (BIG savings!)
update_setting "SEMANTIC_CACHE_ENABLE" "1"

# 3. Set minimum cache score
update_setting "SEMANTIC_CACHE_MIN_SCORE" "0.85"

# Clean up backup files
rm -f "${ENV_FILE}.bak"

echo ""
echo "✅ Cost-saving features enabled!"
echo ""
echo "📊 What's enabled:"
echo "  ✓ LLM features (LLM_DISABLED=false)"
echo "  ✓ Semantic caching (SEMANTIC_CACHE_ENABLE=1)"
echo "  ✓ Cache threshold (SEMANTIC_CACHE_MIN_SCORE=0.85)"
echo ""

# Check if Azure is configured
if grep -q "^AZURE_OPENAI_ENDPOINT=" "$ENV_FILE" && \
   grep -q "^AZURE_OPENAI_KEY=" "$ENV_FILE" && \
   ! grep -q "^AZURE_OPENAI_KEY=your-" "$ENV_FILE"; then
    echo "✅ Azure OpenAI appears to be configured!"
    echo ""
    echo "💡 Recommended: Enable Azure by default:"
    echo "   Add to .env.local: USE_AZURE=1"
    echo ""
    read -p "Enable Azure by default? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        update_setting "USE_AZURE" "1"
        echo "  ✓ Azure enabled by default"
    fi
else
    echo "⚠️  Azure OpenAI not configured yet"
    echo ""
    echo "To use your special Azure pricing, add to .env.local:"
    echo "  AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com"
    echo "  AZURE_OPENAI_KEY=your-key-here"
    echo "  AZURE_OPENAI_DEPLOYMENT=gpt-5-chat"
    echo "  USE_AZURE=1"
fi

echo ""
echo "🚀 Ready to use!"
echo ""
echo "Try it now:"
echo "  ./scripts/claude_wrap.sh \"Say hello\""
echo ""
echo "Or with Azure:"
echo "  ./scripts/claude_wrap.sh --azure \"Say hello\""
echo ""
echo "💡 Pro tips:"
echo "  1. Use --local for simple tasks (FREE)"
echo "  2. Use --route for auto-routing (saves money)"
echo "  3. Semantic cache saves ~50% on repeated questions"
echo "  4. Check logs: tail -f logs/claudelog.txt"
echo ""
echo "📈 Track your savings:"
echo "  grep 'Semantic cache hit' logs/claudelog.txt | wc -l"
echo ""
