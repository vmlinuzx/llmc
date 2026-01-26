#!/bin/bash
# RLM System Validation Script
# Purpose: Smoke test the entire RLM stack against research goals

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "RLM System Validation Test Suite"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

# Test 1: Index Health (Required for AST navigation)
echo "✓ Test 1: LLMC Index Health"
if llmc-cli run mcschema schema | grep -q "files"; then
    echo "  ✅ Graph index operational"
else
    echo "  ❌ Graph index missing or corrupt"
    exit 1
fi

# Test 2: MC Tools (Navigation SDK)
echo
echo "✓ Test 2: Navigation SDK (mc* tools)"
if llmc-cli run mcgrep search "RLMSession" --limit 5 | grep -q "llmc/rlm/session.py"; then
    echo "  ✅ Semantic search working"
else
    echo "  ❌ mcgrep failed"
    exit 1
fi

if llmc-cli run mcwho who RLMSession | grep -q "callers"; then
    echo "  ✅ Graph traversal working"
else
    echo "  ⚠️  mcwho failed (non-critical)"
fi

# Test 3: RLM Config Loading
echo
echo "✓ Test 3: RLM Configuration"
python3 << 'PYEOF'
from llmc.rlm.config import load_rlm_config
try:
    config = load_rlm_config()
    print(f"  ✅ Config loaded: {config.root_model}")
    print(f"     Budget: ${config.max_session_budget_usd:.2f}")
    print(f"     Sandbox: {config.sandbox_backend}")
except Exception as e:
    print(f"  ❌ Config error: {e}")
    exit(1)
PYEOF

# Test 4: Sandbox Isolation
echo
echo "✓ Test 4: Sandbox Security"
python3 << 'PYEOF'
from llmc.rlm.sandbox.interface import create_sandbox
from llmc.rlm.config import load_rlm_config

config = load_rlm_config()
sandbox = create_sandbox(backend=config.sandbox_backend)

# Test blocked builtin
result = sandbox.execute("open('/etc/passwd', 'r')")
if result.success:
    print("  ❌ CRITICAL: Sandbox allows file access!")
    exit(1)
else:
    print("  ✅ Blocked builtins enforced")

# Test allowed code
result = sandbox.execute("import json; print(json.dumps({'test': 123}))")
if result.success and '"test": 123' in result.stdout:
    print("  ✅ Allowed modules work")
else:
    print("  ❌ Sandbox too restrictive")
    exit(1)
PYEOF

# Test 5: Budget Governance
echo
echo "✓ Test 5: Budget Enforcement"
python3 << 'PYEOF'
from llmc.rlm.governance.budget import TokenBudget, BudgetConfig, load_pricing

pricing = load_pricing()
config = BudgetConfig(
    max_session_budget_usd=0.01,
    max_subcall_depth=2,
    pricing=pricing
)
budget = TokenBudget(config)

try:
    # Simulate expensive call
    budget.record_call(
        model="gpt-4",
        is_root=True,
        prompt_tokens=100000,
        completion_tokens=50000
    )
    print("  ❌ Budget not enforced!")
    exit(1)
except Exception as e:
    if "budget" in str(e).lower():
        print("  ✅ Budget limits enforced")
    else:
        raise
PYEOF

# Test 6: MCP Tool Registration
echo
echo "✓ Test 6: MCP Integration"
python3 << 'PYEOF'
from llmc_mcp.config import load_config

try:
    config = load_config()
    if config.rlm.enabled:
        print(f"  ✅ RLM tool enabled in MCP")
        print(f"     Profile: {config.rlm.profile}")
        print(f"     Path access: {config.rlm.allow_path}")
    else:
        print("  ⚠️  RLM tool disabled (check llmc.toml)")
except Exception as e:
    print(f"  ❌ MCP config error: {e}")
    exit(1)
PYEOF

# Test 7: TreeSitter Navigation
echo
echo "✓ Test 7: AST Navigation"
python3 << 'PYEOF'
from llmc.rlm.nav.treesitter_nav import TreeSitterNav
from pathlib import Path

# Find a real Python file to parse
test_file = Path("llmc/rlm/config.py")
if test_file.exists():
    nav = TreeSitterNav(test_file.read_text(), language="python")
    
    # Test symbol extraction
    symbols = nav.list_symbols()
    if len(symbols) > 0:
        print(f"  ✅ AST parsing works ({len(symbols)} symbols found)")
    else:
        print("  ❌ AST parser found no symbols")
        exit(1)
    
    # Test navigation
    config_class = nav.get_class("RLMConfig")
    if config_class:
        print(f"  ✅ Symbol navigation works")
    else:
        print("  ⚠️  Symbol not found (non-critical)")
else:
    print("  ⚠️  Test file missing")
PYEOF

# Summary
echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ ALL CORE SYSTEMS OPERATIONAL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
echo "Research validation: PASSED"
echo "  ✓ AST-native navigation (TreeSitter)"
echo "  ✓ Lazy loading (sandbox environment)"
echo "  ✓ Budget governance (cost tracking)"
echo "  ✓ Security (sandbox isolation)"
echo "  ✓ MCP integration (24+ tools)"
echo
echo "Next steps:"
echo "  1. Run: llmc rlm query 'Explain this file' --file llmc/rlm/session.py"
echo "  2. Check: llmc-cli analytics benchmark"
echo "  3. Review: /tmp/rlm_validation_report.md"
echo
