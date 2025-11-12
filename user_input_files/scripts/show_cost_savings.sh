#!/usr/bin/env bash
# show_cost_savings.sh - Show cost savings from semantic caching and smart routing

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$ROOT/logs/claudelog.txt"

echo "💰 Claude Wrap Cost Savings Report"
echo "==================================="
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo "⚠️  No log file found at: $LOG_FILE"
    echo "Run some claude_wrap.sh commands first!"
    exit 1
fi

# Count cache hits
CACHE_HITS=$(grep "Semantic cache hit" "$LOG_FILE" 2>/dev/null | wc -l | tr -d ' ')
[ -z "$CACHE_HITS" ] && CACHE_HITS=0

# Count different routing types
LOCAL_ROUTES=$(grep "Routing to local Ollama" "$LOG_FILE" 2>/dev/null | wc -l | tr -d ' ')
[ -z "$LOCAL_ROUTES" ] && LOCAL_ROUTES=0

API_ROUTES=$(grep "Routing to Gemini API" "$LOG_FILE" 2>/dev/null | wc -l | tr -d ' ')
[ -z "$API_ROUTES" ] && API_ROUTES=0

CLAUDE_ROUTES=$(grep "Routing to Claude" "$LOG_FILE" 2>/dev/null | wc -l | tr -d ' ')
[ -z "$CLAUDE_ROUTES" ] && CLAUDE_ROUTES=0

AZURE_ROUTES=$(grep "Routing to Claude Code with Azure" "$LOG_FILE" 2>/dev/null | wc -l | tr -d ' ')
[ -z "$AZURE_ROUTES" ] && AZURE_ROUTES=0

# Estimate costs (rough approximations) using awk for float math
LOCAL_COST=0
API_COST=$(awk "BEGIN {printf \"%.2f\", $API_ROUTES * 0.10}")
CLAUDE_COST=$(awk "BEGIN {printf \"%.2f\", $CLAUDE_ROUTES * 0.50}")
AZURE_COST=$(awk "BEGIN {printf \"%.2f\", $AZURE_ROUTES * 0.25}")

TOTAL_COST=$(awk "BEGIN {printf \"%.2f\", $LOCAL_COST + $API_COST + $CLAUDE_COST + $AZURE_COST}")

# Calculate what it would have cost without routing (all Claude)
TOTAL_REQUESTS=$(( LOCAL_ROUTES + API_ROUTES + CLAUDE_ROUTES + AZURE_ROUTES ))
WITHOUT_ROUTING=$(awk "BEGIN {printf \"%.2f\", $TOTAL_REQUESTS * 0.50}")

# Calculate cache savings (assuming each hit saved a $0.30 request)
CACHE_SAVINGS=$(awk "BEGIN {printf \"%.2f\", $CACHE_HITS * 0.30}")

# Total savings
ROUTING_SAVINGS=$(awk "BEGIN {printf \"%.2f\", $WITHOUT_ROUTING - $TOTAL_COST}")
TOTAL_SAVINGS=$(awk "BEGIN {printf \"%.2f\", $ROUTING_SAVINGS + $CACHE_SAVINGS}")

echo "📊 Request Distribution:"
echo "  Local (Ollama):    $LOCAL_ROUTES requests (FREE)"
echo "  API (Gemini):      $API_ROUTES requests (~\$$API_COST)"
echo "  Claude (API):      $CLAUDE_ROUTES requests (~\$$CLAUDE_COST)"
echo "  Azure (OpenAI):    $AZURE_ROUTES requests (~\$$AZURE_COST)"
echo "  ─────────────────────────────────"
echo "  Total:             $TOTAL_REQUESTS requests"
echo ""

echo "💾 Semantic Cache:"
echo "  Cache hits:        $CACHE_HITS (FREE)"
echo "  Estimated savings: \$$CACHE_SAVINGS"
echo ""

echo "💰 Cost Analysis:"
echo "  Actual cost:       ~\$$TOTAL_COST"
echo "  Without routing:   ~\$$WITHOUT_ROUTING (all Claude)"
echo "  ─────────────────────────────────"
echo "  Total savings:     ~\$$TOTAL_SAVINGS"
echo ""

if [ "$TOTAL_REQUESTS" -gt 0 ]; then
    SAVINGS_PERCENT=$(awk "BEGIN {printf \"%.1f\", $TOTAL_SAVINGS * 100 / $WITHOUT_ROUTING}")
    echo "📈 Savings Rate:     ${SAVINGS_PERCENT}%"
    echo ""
fi

# Show recent activity
echo "📝 Recent Activity (last 10):"
grep -E "Routing to|Semantic cache hit" "$LOG_FILE" | tail -10 | sed 's/^/  /'
echo ""

# Recommendations
echo "💡 Recommendations:"
if [ "$CACHE_HITS" -eq 0 ]; then
    echo "  ⚠️  No cache hits yet. Enable: SEMANTIC_CACHE_ENABLE=1"
fi
if [ "$LOCAL_ROUTES" -eq 0 ]; then
    echo "  💡 Try --local for simple tasks (FREE)"
fi
if [ "$API_ROUTES" -lt "$CLAUDE_ROUTES" ]; then
    echo "  💡 Use --route for auto-routing (saves money)"
fi
if [ "$AZURE_ROUTES" -eq 0 ] && [ "$CLAUDE_ROUTES" -gt 0 ]; then
    echo "  💡 Configure Azure for better pricing (50% savings)"
fi

echo ""
echo "🎯 Quick Actions:"
echo "  View full log:     tail -f $LOG_FILE"
echo "  Enable caching:    echo 'SEMANTIC_CACHE_ENABLE=1' >> .env.local"
echo "  Setup Azure:       edit .env.local (see .env.local.example)"
echo "  Try smart routing: ./scripts/claude_wrap.sh --route \"task\""
echo ""
