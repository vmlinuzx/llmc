"""
Tests for Medical Search Pipeline (Phase 3).
"""

import pytest
from typing import List, Optional
from tools.rag.search.medical_search import MedicalSearchPipeline, SearchResult
from tools.rag.embeddings.medical import MedicalEmbeddingManager

class MockVectorDB:
    def query_docs(self, query: str, limit: int) -> List[str]:
        # Return dummy doc IDs
        return ["doc_1", "doc_2", "doc_3"]

    def query_sections(self, query: str, doc_ids: List[str], limit: int) -> List[SearchResult]:
        # Return dummy sections
        # Assume doc_1 has relevant subjective section, but maybe missing assessment in initial retrieval
        return [
            SearchResult(doc_id="doc_1", section_id="s1", content="Subjective...", score=0.9, metadata={"section_type": "subjective"}),
            SearchResult(doc_id="doc_2", section_id="s2", content="Assessment...", score=0.8, metadata={"section_type": "assessment"}),
        ]

    def get_section(self, doc_id: str, section_type: str) -> Optional[SearchResult]:
        # Mock fetching missing sections
        if doc_id == "doc_1" and section_type == "assessment":
            return SearchResult(doc_id="doc_1", section_id="s3", content="Assessment Doc 1", score=0.5, metadata={"section_type": "assessment"})
        if doc_id == "doc_1" and section_type == "plan":
             return SearchResult(doc_id="doc_1", section_id="s4", content="Plan Doc 1", score=0.5, metadata={"section_type": "plan"})
        return None

class MockEmbedder:
    def get_embedding_function(self, profile: str):
        return lambda x: [[0.1, 0.2]] # Dummy vector

def test_pipeline_flow():
    db = MockVectorDB()
    embedder = MockEmbedder()
    pipeline = MedicalSearchPipeline(embedder, db)
    
    results = pipeline.search("test query", top_k=5)
    
    # 1. Verify Stage 2 results are present
    assert any(r.content == "Subjective..." for r in results)
    
    # 2. Verify Tail Capture: doc_1 was top doc, but subjective was only returned by query_sections.
    # The pipeline should have injected doc_1's Assessment and Plan.
    assert any(r.content == "Assessment Doc 1" for r in results)
    assert any(r.content == "Plan Doc 1" for r in results)
    
    # 3. Verify sorting (rerank mock sorts by score)
    # Subjective (0.9) > Assessment Doc 2 (0.8) > Injected (0.5)
    assert results[0].score >= results[1].score

def test_longcontext_adapter_init(tmp_path):
    # Verify adapter loads config
    from tools.rag.embeddings.hf_longcontext_adapter import LongContextAdapter
    
    config_file = tmp_path / "config.json"
    config_file.write_text('{"model_name": "test/model", "max_seq_tokens": 128}')
    
    adapter = LongContextAdapter(config_file)
    assert adapter.model_name == "test/model"
    assert adapter.max_length == 128
