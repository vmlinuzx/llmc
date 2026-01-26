#!/usr/bin/env python3
"""Simple RLM smoke test - just proves it works."""

import asyncio
from pathlib import Path

from llmc.rlm.config import load_rlm_config
from llmc.rlm.session import RLMSession


async def main():
    print("🧪 RLM Smoke Test\n")
    
    # Load config
    config = load_rlm_config()
    config.root_model = "deepseek/deepseek-chat"
    config.sub_model = "deepseek/deepseek-chat"
    config.max_session_budget_usd = 0.10
    config.trace_enabled = False  # Faster
    
    # Create session
    print("✓ Creating RLM session...")
    session = RLMSession(config)
    
    # Load a real file
    target = Path("/home/vmlinux/src/llmc/llmc/rlm/config.py")
    print(f"✓ Loading file: {target.name}")
    session.load_code_context(target)
    
    # Simple query
    print("✓ Running query...")
    result = await session.run(
        task="What is the default max_session_budget_usd value? Just give me the number.",
        max_turns=3
    )
    
    # Show results
    print(f"\n{'='*60}")
    print(f"Success: {result.success}")
    print(f"Answer: {result.answer}")
    print("\nBudget:")
    if result.budget_summary:
        print(f"  Tokens: {result.budget_summary.get('total_tokens', 0):,}")
        print(f"  Cost: ${result.budget_summary.get('total_cost_usd', 0):.4f}")
        print(f"  Subcalls: {result.budget_summary.get('sub_calls', 0)}")
    print(f"{'='*60}")
    
    # Validation
    if result.success and "1.00" in (result.answer or ""):
        print("\n✅ RLM WORKS! Answer contains '1.00'")
        return 0
    else:
        print("\n⚠️  RLM ran but answer may be incorrect")
        return 1

if __name__ == "__main__":
    exit(asyncio.run(main()))
