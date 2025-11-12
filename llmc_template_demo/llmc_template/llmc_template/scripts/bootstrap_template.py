#!/usr/bin/env python3
"""
Bootstrap script for LLM Commander template.
Sets up the environment and creates necessary directories.
"""

import os
import sys
from pathlib import Path

def main():
    print("🤖 LLM Commander Template Bootstrap")
    print("=" * 40)
    
    # Create runtime directories
    runtime_dirs = [
        ".llmc",
        ".llmc/index", 
        ".llmc/cache",
        ".llmc/logs"
    ]
    
    for dir_path in runtime_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created {dir_path}/")
    
    # Copy local config if it doesn't exist
    local_config = Path("config/local.toml")
    if not local_config.exists():
        example_config = Path("config/local.example.toml")
        if example_config.exists():
            shutil.copy2(example_config, local_config)
            print("✓ Created config/local.toml from example")
        else:
            print("⚠ No local.example.toml found")
    
    # Validate configuration
    print("\n📋 Validating configuration...")
    try:
        import toml
        with open("config/default.toml") as f:
            config = toml.load(f)
        print("✓ Default configuration is valid")
    except ImportError:
        print("⚠ toml not installed - run: pip install toml")
    except Exception as e:
        print(f"⚠ Configuration error: {e}")
    
    print("\n🎉 Bootstrap completed!")
    print("\nNext steps:")
    print("1. Edit config/local.toml if needed")
    print("2. Run ./scripts/rag_refresh.sh to index your codebase")
    print("3. Start using LLM Commander!")

if __name__ == "__main__":
    import shutil
    main()
