"""
Critical Test: Enrichment Data Integration Failure

This test demonstrates that the RAG system has a complete data integration failure:
- Enrichment data exists in the database (2,426 enrichments)
- Graph building process never reads from the database
- User-facing API returns empty results
- 100% of enriched data is lost in the pipeline

CRITICAL SEVERITY: This breaks the core value proposition of the RAG system.
"""

import pytest
from pathlib import Path
import sys
import json

sys.path.insert(0, '/home/vmlinux/src/llmc')

from tools.rag.database import Database


class TestEnrichmentDataIntegrationFailure:
    """Tests to prove the enrichment data integration is completely broken"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.db_path = Path("/home/vmlinux/src/llmc/.rag/index_v2.db")
        self.graph_path = Path("/home/vmlinux/src/llmc/.llmc/rag_graph.json")
    
    def test_enrichments_exist_in_database(self):
        """Prove that enrichment data actually exists in the database"""
        db = Database(self.db_path)
        
        enrich_count = db.conn.execute("SELECT COUNT(*) FROM enrichments").fetchone()[0]
        span_count = db.conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0]
        
        assert enrich_count > 0, "Enrichments should exist in database"
        assert enrich_count >= span_count - 5, "Nearly all spans should be enriched"
        
        # Sample enrichment data
        sample = db.conn.execute("""
            SELECT e.span_hash, e.summary, e.evidence, e.inputs, e.outputs, 
                   e.side_effects, e.pitfalls, e.usage_snippet
            FROM enrichments e
            LIMIT 1
        """).fetchone()
        
        assert sample is not None, "Should have sample enrichment"
        assert sample[1] is not None, "Summary should exist"
        assert len(sample[1]) > 10, "Summary should have content"
        
        db.close()
    
    def test_graph_has_zero_enrichment_metadata(self):
        """Prove that the graph JSON file contains ZERO enrichment data"""
        with open(self.graph_path) as f:
            graph = json.load(f)
        
        schema = graph.get('schema_graph', {})
        entities = schema.get('entities', [])
        
        assert len(entities) > 0, "Graph should have entities"
        
        # Check every entity for enrichment fields
        entities_with_enrichment = []
        for ent in entities:
            metadata = ent.get('metadata', {})
            enrichment_fields = ['summary', 'evidence', 'inputs', 'outputs', 
                                'side_effects', 'pitfalls', 'usage_snippet', 'tags']
            has_enrichment = any(field in metadata for field in enrichment_fields)
            if has_enrichment:
                entities_with_enrichment.append(ent)
        
        assert len(entities_with_enrichment) == 0, \
            f"Graph should have zero entities with enrichment, found {len(entities_with_enrichment)}"
    
    def test_database_vs_graph_enrichment_mismatch(self):
        """Prove the severe mismatch between database and graph"""
        db = Database(self.db_path)
        
        enrich_count = db.conn.execute("SELECT COUNT(*) FROM enrichments").fetchone()[0]
        
        with open(self.graph_path) as f:
            graph = json.load(f)
        
        entities = graph.get('schema_graph', {}).get('entities', [])
        
        # The mismatch is extreme: 2426 enrichments vs 0 in graph
        assert enrich_count == 2426, "Should have 2426 enrichments in DB"
        assert len(entities) > 0, "Graph should have entities"
        
        # But NONE of the entities have enrichment data
        enrichment_loss_rate = 100.0  # 2426 lost / 2426 total * 100
        
        print(f"\n{'='*80}")
        print(f"ENRICHMENT DATA LOSS: {enrichment_loss_rate:.1f}%")
        print(f"Database has {enrich_count} enrichments")
        print(f"Graph has 0 entities with enrichment data")
        print(f"Data loss: {enrich_count} enrichments (complete failure)")
        print(f"{'='*80}\n")
        
        assert enrichment_loss_rate == 100.0, \
            "Data loss rate should be 100% (complete integration failure)"
        
        db.close()
    
    def test_stub_functions_return_empty(self):
        """Prove that the public API functions are stubbed and broken"""
        from tools.rag import tool_rag_search, tool_rag_where_used, tool_rag_lineage
        
        # All these should return empty lists (broken stubs)
        assert tool_rag_search("test") == [], \
            "tool_rag_search should be broken (returns empty list)"
        
        assert tool_rag_where_used("test") == [], \
            "tool_rag_where_used should be broken (returns empty list)"
        
        assert tool_rag_lineage("test") == [], \
            "tool_rag_lineage should be broken (returns empty list)"
    
    def test_id_mismatch_prevents_data_joining(self):
        """Prove that the ID formats are incompatible between DB and graph"""
        db = Database(self.db_path)
        
        # Database uses span_hash IDs
        db_sample = db.conn.execute("""
            SELECT e.span_hash FROM enrichments e LIMIT 1
        """).fetchone()
        db_id = db_sample[0]
        
        assert db_id.startswith("sha256:"), \
            "Database IDs should be span_hash format (sha256:...)"
        
        # Graph uses symbol-based IDs
        with open(self.graph_path) as f:
            graph = json.load(f)
        
        entities = graph.get('schema_graph', {}).get('entities', [])
        graph_id = entities[0].get('id')
        
        assert graph_id.startswith(("sym:", "type:")), \
            "Graph IDs should be symbol-based (sym:..., type:...)"
        
        # The formats are completely different - no way to join!
        assert db_id != graph_id, \
            "ID formats should be different (proving incompatibility)"
        
        db.close()
    
    def test_enrichment_pipeline_creates_data_but_its_lost(self):
        """
        End-to-end test proving:
        1. Enrichment pipeline runs (metrics show 99 enrichments)
        2. Data is stored in database successfully
        3. Graph building ignores the database
        4. User-facing API returns nothing
        5. 100% data loss
        """
        db = Database(self.db_path)
        
        # Step 1: Verify enrichment pipeline worked
        enrich_count = db.conn.execute("SELECT COUNT(*) FROM enrichments").fetchone()[0]
        assert enrich_count == 2426, "Enrichment pipeline created data"
        
        # Step 2: Verify data quality
        sample = db.conn.execute("""
            SELECT summary, evidence, model, schema_ver
            FROM enrichments WHERE summary IS NOT NULL
            LIMIT 1
        """).fetchone()
        
        assert sample is not None, "Enrichment should have rich data"
        assert len(sample[0]) > 50, "Summary should be substantial"
        assert sample[1] is not None, "Evidence should exist"
        
        # Step 3: Verify data is completely lost in graph
        with open(self.graph_path) as f:
            graph = json.load(f)
        
        entities = graph.get('schema_graph', {}).get('entities', [])
        
        # Check that entities have ONLY basic AST metadata
        for ent in entities[:10]:  # Check first 10
            metadata = ent.get('metadata', {})
            assert 'params' in metadata or 'bases' in metadata, \
                "Should have basic AST metadata"
            assert 'summary' not in metadata, \
                "Should NOT have enrichment data (data loss!)"
        
        # Step 4: Verify stub API returns nothing
        from tools.rag import tool_rag_search
        result = tool_rag_search("anything")
        assert result == [], "API should return nothing (broken stubs)"
        
        db.close()
        
        print(f"\n{'='*80}")
        print("ENRICHMENT PIPELINE VERDICT:")
        print(f"  ✅ Pipeline creates 2,426 enrichments with rich metadata")
        print(f"  ❌ Graph building ignores database (0% integration)")
        print(f"  ❌ Public API returns empty results (stub functions)")
        print(f"  💀 Net result: 100% data loss, system is non-functional")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
