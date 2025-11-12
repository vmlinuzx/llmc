#!/usr/bin/env python3
"""
Test schema extraction on LLMC Python files
"""

import sys
from pathlib import Path

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent / "tools"))

from rag.schema import extract_schema_from_file, build_schema_graph

def test_single_file():
    """Test extraction on a single file"""
    test_file = Path("/home/vmlinux/src/llmc/tools/rag/indexer.py")
    
    print(f"Testing schema extraction on: {test_file}")
    print("=" * 60)
    
    entities, relations = extract_schema_from_file(test_file)
    
    print(f"\n✅ Extracted {len(entities)} entities and {len(relations)} relations\n")
    
    print("ENTITIES:")
    print("-" * 60)
    for entity in entities[:10]:  # Show first 10
        print(f"  {entity.kind:10} | {entity.id}")
        if entity.metadata:
            print(f"             | metadata: {entity.metadata}")
    
    if len(entities) > 10:
        print(f"  ... and {len(entities) - 10} more entities")
    
    print("\nRELATIONS:")
    print("-" * 60)
    for relation in relations[:15]:  # Show first 15
        print(f"  {relation.src} --[{relation.edge}]--> {relation.dst}")
    
    if len(relations) > 15:
        print(f"  ... and {len(relations) - 15} more relations")

def test_multiple_files():
    """Test building a graph from multiple files"""
    repo_root = Path("/home/vmlinux/src/llmc")
    test_files = [
        repo_root / "tools/rag/schema.py",
        repo_root / "tools/rag/indexer.py",
        repo_root / "tools/rag/database.py",
    ]
    
    print("\n\n" + "=" * 60)
    print("Testing graph building on multiple files")
    print("=" * 60)
    
    graph = build_schema_graph(repo_root, test_files)
    
    print(f"\n✅ Built graph with:")
    print(f"   - {len(graph.entities)} unique entities")
    print(f"   - {len(graph.relations)} unique relations")
    print(f"   - Indexed at: {graph.indexed_at}")
    
    # Save to test file
    output_path = Path("/tmp/test_schema_graph.json")
    graph.save(output_path)
    print(f"\n💾 Saved graph to: {output_path}")

if __name__ == "__main__":
    try:
        test_single_file()
        test_multiple_files()
        print("\n✅ ALL TESTS PASSED!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
