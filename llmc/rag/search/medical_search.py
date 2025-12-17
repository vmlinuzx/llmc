"""
Two-Stage Medical Search Pipeline.
Stage 1: Document retrieval (Coarse)
Stage 2: Section retrieval (Fine) + Reranking
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class SearchResult:
    doc_id: str
    section_id: str
    content: str
    score: float
    metadata: dict[str, Any]


class MedicalSearchPipeline:
    def __init__(self, embedding_manager, vector_db):
        """
        embedding_manager: Instance of MedicalEmbeddingManager
        vector_db: Database interface for retrieval (Mockable)
        """
        self.embedder = embedding_manager
        self.db = vector_db

    def search(self, query: str, top_k: int = 10) -> list[SearchResult]:
        # Stage 1: Document Retrieval (Long Context)
        # Embed query using doc profile (assumes query is long enough or we use same model)
        # Note: Often Stage 1 uses sparse search (BM25) or doc-embedding.
        # SDD says: "Stage1 (doc-level) -> Stage2 (section-level)"

        # 1. Get candidate documents via "medical_doc" index
        # For query embedding, we usually use the same model.
        # Clinical-Longformer for query might be overkill or mismatched if query is short.
        # SDD 3.2 mentions "Stage1 (doc-level candidates)"

        # Let's assume we retrieve top DOC_K documents based on doc-level vectors
        doc_k = 50
        # doc_query_vec = self.embedder.get_embedding_function("medical_doc")(query)[0]
        # candidate_doc_ids = self.db.search_index("emb_medical_doc", doc_query_vec, limit=doc_k)

        # MOCK LOGIC for Pipeline Skeleton (since we don't have a running DB with data yet)
        candidate_doc_ids = self._stage1_retrieve(query, limit=doc_k)

        # Stage 2: Section Retrieval (Fine)
        # Embed query using "medical" profile (Ollama/BGE-M3)
        # section_query_vec = self.embedder.get_embedding_function("medical")(query)[0]

        # Filter sections by candidate_doc_ids to scope the search
        results = self._stage2_retrieve(
            query, candidate_docs=candidate_doc_ids, limit=top_k
        )

        # Tail Capture: Force include Assessment/Plan from top Stage 1 docs
        results = self._apply_tail_capture(results, candidate_doc_ids)

        # Rerank (Placeholder for "bge-reranker-v2-m3")
        results = self._rerank(query, results)

        return results[:top_k]

    def _stage1_retrieve(self, query: str, limit: int) -> list[str]:
        # Implementation would call DB
        return self.db.query_docs(query, limit)

    def _stage2_retrieve(
        self, query: str, candidate_docs: list[str], limit: int
    ) -> list[SearchResult]:
        # Implementation would call DB with filter
        return self.db.query_sections(query, doc_ids=candidate_docs, limit=limit)

    def _apply_tail_capture(
        self, current_results: list[SearchResult], candidate_docs: list[str]
    ) -> list[SearchResult]:
        """
        Ensure Assessment/Plan sections from top documents are included.
        """
        # Identify docs in Stage 1 but missing key sections in Stage 2 results
        # Fetch Assessment/Plan for those docs and inject them

        existing_keys = {
            (r.doc_id, r.metadata.get("section_type")) for r in current_results
        }

        # For top 3 docs from Stage 1
        for doc_id in candidate_docs[:3]:
            if (doc_id, "assessment") not in existing_keys:
                # Fetch assessment
                section = self.db.get_section(doc_id, "assessment")
                if section:
                    current_results.append(section)

            if (doc_id, "plan") not in existing_keys:
                # Fetch plan
                section = self.db.get_section(doc_id, "plan")
                if section:
                    current_results.append(section)

        return current_results

    def _rerank(self, query: str, results: list[SearchResult]) -> list[SearchResult]:
        # Placeholder for reranker logic
        # Sort by score for now
        return sorted(results, key=lambda x: x.score, reverse=True)
