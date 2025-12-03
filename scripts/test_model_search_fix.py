#!/usr/bin/env python3
"""
Test script to verify the "model" search bug is fixed.
Run this directly to test without MCP layers.
"""

from pathlib import Path
import sys

# Add repo to path
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))

from tools.rag.search import search_spans

# Test 1: Direct search
print("="*60)
print("TEST 1: Direct search_spans for 'model'")
print("="*60)

results = search_spans("model", limit=5, repo_root=repo_root)
print(f"\nResults: {len(results)}")

if results:
    print("✅ SUCCESS - 'model' returns results!\n")
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r.symbol}")
        print(f"     Score: {r.score:.3f}")
        print(f"     Path: {r.path}")
        print()
else:
    print("❌ FAILED - Still returning 0 results")
    sys.exit(1)

# Test 2: Config hot-reload
print("="*60)
print("TEST 2: Config hot-reload (edit llmc.toml)")
print("="*60)

from tools.rag.config import load_config

config_file = repo_root / "llmc.toml"
original = config_file.read_text()

# Edit
modified = original.replace(
    'default_profile = "docs"',
    'default_profile = "code"  # HOTRELOAD_TEST'
)
config_file.write_text(modified)
print("\n✓ Config edited")

# Load and check
import time
time.sleep(0.1)
config = load_config(repo_root)
default_profile = config.get("embeddings", {}).get("default_profile")

# Revert
config_file.write_text(original)

if default_profile == "code":
    print("✅ SUCCESS - Config change picked up immediately!\n")
else:
    print(f"❌ FAILED - Still shows: {default_profile}")
    sys.exit(1)

print("="*60)
print("🎉 ALL TESTS PASSED!")
print("="*60)
print("\nThe bugs are fixed:")
print("  ✓ 'model' keyword returns search results")
print("  ✓ Config hot-reload works (no daemon restart needed)")
