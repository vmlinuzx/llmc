#!/usr/bin/env python3
"""
Quick verification script for Phase 1 implementation.
Demonstrates config loading and type validation.
"""

import toml
from pathlib import Path
from llmc.docgen import load_docgen_backend, DocgenResult
from llmc.docgen.config import get_output_dir, get_require_rag_fresh


def main():
    print("=" * 60)
    print("Docgen Phase 1 Verification")
    print("=" * 60)
    
    # Load llmc.toml
    repo_root = Path(__file__).parent.parent
    toml_path = repo_root / "llmc.toml"
    
    print(f"\n📄 Loading config from: {toml_path}")
    with open(toml_path, "r") as f:
        toml_data = toml.load(f)
    
    # Test config loading
    print("\n🔧 Testing config loading...")
    backend = load_docgen_backend(repo_root, toml_data)
    print(f"   Backend loaded: {backend}")
    print(f"   (None is expected since enabled=false)")
    
    # Test helper functions
    print("\n📁 Testing helper functions...")
    output_dir = get_output_dir(toml_data)
    print(f"   Output directory: {output_dir}")
    
    require_rag = get_require_rag_fresh(toml_data)
    print(f"   Require RAG fresh: {require_rag}")
    
    # Test DocgenResult
    print("\n📊 Testing DocgenResult types...")
    
    result_noop = DocgenResult(
        status="noop",
        sha256="abc123",
        output_markdown=None,
        reason="SHA unchanged"
    )
    print(f"   NOOP result: {result_noop.status} - {result_noop.reason}")
    
    result_generated = DocgenResult(
        status="generated",
        sha256="def456",
        output_markdown="# Test Doc\n\nContent here",
        reason=None
    )
    print(f"   Generated result: {result_generated.status}")
    
    result_skipped = DocgenResult(
        status="skipped",
        sha256="ghi789",
        output_markdown=None,
        reason="Not indexed in RAG"
    )
    print(f"   Skipped result: {result_skipped.status} - {result_skipped.reason}")
    
    # Test invalid status
    print("\n❌ Testing invalid status (should raise ValueError)...")
    try:
        DocgenResult(
            status="invalid",
            sha256="xyz",
            output_markdown=None
        )
        print("   ERROR: Should have raised ValueError!")
    except ValueError as e:
        print(f"   ✅ Correctly raised: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Phase 1 verification complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
