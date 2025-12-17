"""
Tests for Medical Search Pipeline (Phase 3).
"""

import pytest

from llmc.rag.eval.medical_eval import MedicalEvaluator
from llmc.rag.search.medical_search import MedicalSearchPipeline, SearchResult
from llmc.rag.search.section_priority import (
    SearchResult as SectionPriorityResult,
    SectionPriority,
)


class MockVectorDB:
    def query_docs(self, query: str, limit: int) -> list[str]:
        # Return dummy doc IDs
        return ["doc_1", "doc_2", "doc_3"]

    def query_sections(
        self, query: str, doc_ids: list[str], limit: int
    ) -> list[SearchResult]:
        # Return dummy sections
        # Assume doc_1 has relevant subjective section, but maybe missing assessment in initial retrieval
        return [
            SearchResult(
                doc_id="doc_1",
                section_id="s1",
                content="Subjective...",
                score=0.9,
                metadata={"section_type": "subjective"},
            ),
            SearchResult(
                doc_id="doc_2",
                section_id="s2",
                content="Assessment...",
                score=0.8,
                metadata={"section_type": "assessment"},
            ),
        ]

    def get_section(self, doc_id: str, section_type: str) -> SearchResult | None:
        # Mock fetching missing sections
        if doc_id == "doc_1" and section_type == "assessment":
            return SearchResult(
                doc_id="doc_1",
                section_id="s3",
                content="Assessment Doc 1",
                score=0.5,
                metadata={"section_type": "assessment"},
            )
        if doc_id == "doc_1" and section_type == "plan":
            return SearchResult(
                doc_id="doc_1",
                section_id="s4",
                content="Plan Doc 1",
                score=0.5,
                metadata={"section_type": "plan"},
            )
        return None


class MockEmbedder:
    def get_embedding_function(self, profile: str):
        return lambda x: [[0.1, 0.2]]  # Dummy vector


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
    from llmc.rag.embeddings.hf_longcontext_adapter import LongContextAdapter

    config_file = tmp_path / "config.json"
    config_file.write_text('{"model_name": "test/model", "max_seq_tokens": 128}')

    adapter = LongContextAdapter(config_file)
    assert adapter.model_name == "test/model"
    assert adapter.max_length == 128


def test_section_priority_boosts():
    """Test section priority boosting."""
    # Create test results with different section types
    results = [
        SectionPriorityResult(
            doc_id="doc1",
            section_id="s1",
            content="Technique description",
            score=0.9,
            metadata={"section_type": "TECHNIQUE"},
        ),
        SectionPriorityResult(
            doc_id="doc2",
            section_id="s2",
            content="Impression summary",
            score=0.8,
            metadata={"section_type": "IMPRESSION"},
        ),
        SectionPriorityResult(
            doc_id="doc3",
            section_id="s3",
            content="Findings details",
            score=0.7,
            metadata={"section_type": "FINDINGS"},
        ),
    ]

    # Apply section-based boosting
    boosted = SectionPriority.boost_by_section(results)

    # Check ordering: IMPRESSION (0.8 * 1.0 = 0.8) should be first
    # FINDINGS (0.7 * 0.8 = 0.56) second, TECHNIQUE (0.9 * 0.3 = 0.27) third
    assert boosted[0].metadata["section_type"] == "IMPRESSION"
    assert boosted[1].metadata["section_type"] == "FINDINGS"
    assert boosted[2].metadata["section_type"] == "TECHNIQUE"

    # Verify scores are correctly boosted
    assert boosted[0].score == pytest.approx(0.8)
    assert boosted[1].score == pytest.approx(0.56)
    assert boosted[2].score == pytest.approx(0.27)


def test_negation_aware_boost():
    """Test negation detection and boosting."""
    results = [
        SectionPriorityResult(
            doc_id="doc1",
            section_id="s1",
            content="No evidence of pneumonia. The patient denies cough.",
            score=0.9,
            metadata={"section_type": "FINDINGS"},
        ),
        SectionPriorityResult(
            doc_id="doc2",
            section_id="s2",
            content="Positive for COVID-19 infection. Shows clear symptoms.",
            score=0.8,
            metadata={"section_type": "IMPRESSION"},
        ),
        SectionPriorityResult(
            doc_id="doc3",
            section_id="s3",
            content="Normal chest X-ray without any abnormalities.",
            score=0.7,
            metadata={"section_type": "FINDINGS"},
        ),
    ]

    boosted = SectionPriority.negation_aware_boost(results)

    # The affirmed result should be ranked highest despite lower original score
    # Check that doc2 (affirmed) is first
    assert "Positive" in boosted[0].content
    assert boosted[0].metadata["affirmation_detected"] == "True"

    # Negated results should be demoted
    for result in boosted:
        if "No evidence" in result.content:
            assert result.metadata["negation_detected"] == "True"
            # Should be ranked lower
            assert result.score < boosted[0].score


def test_evaluation_metrics():
    """Test medical evaluation metrics."""
    evaluator = MedicalEvaluator()

    # Test data
    predictions = [
        ["doc2", "doc1", "doc3", "doc4"],
        ["doc1", "doc3", "doc5", "doc2"],
        ["doc4", "doc5", "doc6", "doc1"],
    ]
    ground_truth = [["doc1", "doc2"], ["doc1"], ["doc7", "doc8"]]

    # Test Recall@K
    recall_at_2 = evaluator.compute_recall_at_k(predictions, ground_truth, k=2)
    # For first query: top 2 are doc2, doc1 -> both relevant -> recall 1.0
    # Second query: top 2 are doc1, doc3 -> only doc1 relevant -> recall 0.5
    # Third query: top 2 are doc4, doc5 -> none relevant -> recall 0.0
    expected_recall_at_2 = (1.0 + 0.5 + 0.0) / 3
    assert recall_at_2 == pytest.approx(expected_recall_at_2)

    # Test MRR
    mrr = evaluator.compute_mrr(predictions, ground_truth)
    # First query: doc2 at rank 1 is relevant -> 1/1 = 1.0
    # Second query: doc1 at rank 1 -> 1/1 = 1.0
    # Third query: no relevant in predictions -> 0.0
    expected_mrr = (1.0 + 1.0 + 0.0) / 3
    assert mrr == pytest.approx(expected_mrr)

    # Test Precision@K
    precision_at_3 = evaluator.compute_precision_at_k(predictions, ground_truth, k=3)
    # First query: top 3 are doc2, doc1, doc3 -> 2 relevant -> 2/3 ≈ 0.6667
    # Second query: top 3 are doc1, doc3, doc5 -> 1 relevant -> 1/3 ≈ 0.3333
    # Third query: top 3 are doc4, doc5, doc6 -> 0 relevant -> 0.0
    expected_precision_at_3 = (2 / 3 + 1 / 3 + 0.0) / 3
    assert precision_at_3 == pytest.approx(expected_precision_at_3)

    # Test Average Precision
    map_score = evaluator.compute_average_precision(predictions, ground_truth)
    # This is more complex, just ensure it's a valid float
    assert isinstance(map_score, float)
    assert 0.0 <= map_score <= 1.0
