
import sys
from pathlib import Path
import os

# Add repo root to path
repo_root = Path.cwd()
sys.path.insert(0, str(repo_root))

try:
    from tools.rag.config_enrichment import load_enrichment_config
except ImportError:
    print("Failed to import load_enrichment_config")
    sys.exit(1)

try:
    config = load_enrichment_config(repo_root)
    print(f"Loaded config: {config}")
    print(f"Chains: {config.chains.keys()}")
    for name, chain in config.chains.items():
        print(f"Chain '{name}':")
        for spec in chain:
            print(f"  - Name: {spec.name}, Provider: {spec.provider}, URL: {spec.url}")
except Exception as e:
    print(f"Error loading config: {e}")
