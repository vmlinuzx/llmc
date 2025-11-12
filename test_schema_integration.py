#!/usr/bin/env python3
"""
Test graph storage, traversal, and enrichment
"""

import sys
from pathlib import Path

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent / "tools"))

from rag.schema import build_schema_graph
from rag.graph import GraphStore
from rag.enrichment import QueryAnalyzer, HybridRetriever, EnrichmentFeatures
from rag.types import SpanRecord


def test_graph_storage():
    """Test graph loading and storage"""
    print("=" * 60)
    print("TEST 1: Graph Storage and Loading")
    print("=" * 60)
    
    # Build a test graph
    repo_root = Path("/home/vmlinux/src/llmc")
    test_files = [
        repo_root / "tools/rag/schema.py",
        repo_root / "tools/rag/indexer.py",
    ]
    
    schema_graph = build_schema_graph(repo_root, test_files)
    print(f"✅ Built schema graph with {len(schema_graph.entities)} entities")
    
    # Load into graph store
    graph_store = GraphStore()
    graph_store.load_from_schema(schema_graph)
    
    stats = graph_store.get_statistics()
    print(f"\n📊 Graph Statistics:")
    print(f"   Total entities: {stats['total_entities']}")
    print(f"   Total edges: {stats['total_edges']}")
    print(f"   Entity kinds: {stats['entity_kinds']}")
    print(f"   Edge types: {stats['edge_types']}")
    
    return graph_store


def test_graph_traversal(graph_store):
    """Test graph neighbor traversal"""
    print("\n" + "=" * 60)
    print("TEST 2: Graph Traversal")
    print("=" * 60)
    
    # Find an entity to test with
    test_entities = list(graph_store.entities.keys())[:5]
    
    if not test_entities:
        print("⚠️  No entities found in graph")
        return
    
    test_entity = test_entities[0]
    print(f"\n🔍 Testing traversal from: {test_entity}")
    
    # 1-hop traversal
    neighbors_1hop = graph_store.get_neighbors(test_entity, max_hops=1)
    print(f"\n1-hop neighbors ({len(neighbors_1hop)}):")
    for neighbor in neighbors_1hop[:5]:
        print(f"   {neighbor.entity_id}")
        print(f"      └─ via {neighbor.edge_type} (distance={neighbor.distance})")
    
    if len(neighbors_1hop) > 5:
        print(f"   ... and {len(neighbors_1hop) - 5} more")
    
    # 2-hop traversal
    neighbors_2hop = graph_store.get_neighbors(test_entity, max_hops=2)
    print(f"\n2-hop neighbors ({len(neighbors_2hop)}):")
    for neighbor in neighbors_2hop[:5]:
        print(f"   {neighbor.entity_id}")
        print(f"      └─ via {neighbor.edge_type} (distance={neighbor.distance})")
    
    if len(neighbors_2hop) > 5:
        print(f"   ... and {len(neighbors_2hop) - 5} more")


def test_query_analyzer(graph_store):
    """Test query analysis and entity detection"""
    print("\n" + "=" * 60)
    print("TEST 3: Query Analysis")
    print("=" * 60)
    
    analyzer = QueryAnalyzer(graph_store)
    
    test_queries = [
        "Which functions call getUserData?",
        "What breaks if I change the database schema?",
        "Show me all classes that extend BaseModel",
        "How do I make a sandwich?",  # Non-relationship query
    ]
    
    for query in test_queries:
        print(f"\n📝 Query: '{query}'")
        features = analyzer.analyze(query)
        
        print(f"   Relation task: {features.relation_task}")
        print(f"   Detected entities: {features.detected_entities[:3]}")  # Show first 3
        print(f"   Graph coverage: {features.graph_coverage:.2f}")
        print(f"   Complexity score: {features.complexity_score}/10")


def test_hybrid_retrieval(graph_store):
    """Test hybrid retrieval (vector + graph)"""
    print("\n" + "=" * 60)
    print("TEST 4: Hybrid Retrieval")
    print("=" * 60)
    
    analyzer = QueryAnalyzer(graph_store)
    retriever = HybridRetriever(graph_store, analyzer)
    
    # Mock some vector search results
    mock_vector_results = [
        SpanRecord(
            file_path=Path("/test/file1.py"),
            lang="python",
            symbol="getUserData",
            kind="function",
            start_line=10,
            end_line=15,
            byte_start=200,
            byte_end=350,
            span_hash="vec_1",
        ),
        SpanRecord(
            file_path=Path("/test/file2.py"),
            lang="python",
            symbol="UserService",
            kind="class",
            start_line=20,
            end_line=30,
            byte_start=500,
            byte_end=700,
            span_hash="vec_2",
        ),
    ]
    
    query = "Which functions call getUserData?"
    
    print(f"\n📝 Query: '{query}'")
    print(f"📊 Mock vector results: {len(mock_vector_results)}")
    
    merged_results, features = retriever.retrieve(
        query=query,
        vector_results=mock_vector_results,
        max_graph_results=10,
        max_hops=1
    )
    
    print(f"\n✅ Hybrid retrieval complete:")
    print(f"   Total results: {len(merged_results)}")
    print(f"   Relation density: {features.relation_density:.2f}")
    print(f"   Graph coverage: {features.graph_coverage:.2f}")
    print(f"   Complexity: {features.complexity_score}/10")
    
    if features.fallback_reason:
        print(f"   ⚠️  Fallback: {features.fallback_reason}")


def test_routing_features(graph_store):
    """Test enrichment features for router integration"""
    print("\n" + "=" * 60)
    print("TEST 5: Router Integration Features")
    print("=" * 60)
    
    analyzer = QueryAnalyzer(graph_store)
    
    # Test queries with different characteristics
    test_cases = [
        ("Which services call the auth API?", "Should route to LOCAL"),
        ("Write me a hello world program", "Should route normally"),
        ("Trace all database dependencies for the order system", "Complex, may escalate"),
    ]
    
    for query, expected in test_cases:
        features = analyzer.analyze(query)
        
        print(f"\n📝 Query: '{query}'")
        print(f"   Expected: {expected}")
        print(f"   Features:")
        print(f"      relation_task: {features.relation_task}")
        print(f"      complexity: {features.complexity_score}/10")
        print(f"      graph_coverage: {features.graph_coverage:.2f}")
        
        # Simple routing logic (matching the roadmap rules)
        if features.relation_task and features.graph_coverage > 0.8 and features.complexity_score < 7:
            tier = "LOCAL"
        elif features.relation_task and features.complexity_score >= 7:
            tier = "PREMIUM"
        elif features.relation_task:
            tier = "API"
        else:
            tier = "BASELINE"
        
        print(f"      → Suggested tier: {tier}")


if __name__ == "__main__":
    try:
        print("\n🧪 SCHEMA RAG INTEGRATION TESTS")
        print("=" * 60)
        
        # Run tests
        graph_store = test_graph_storage()
        test_graph_traversal(graph_store)
        test_query_analyzer(graph_store)
        test_hybrid_retrieval(graph_store)
        test_routing_features(graph_store)
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
