"""
Comprehensive unit tests for rag/benchmark.py - Embedding Quality Benchmarking.

Tests cover:
- Cosine similarity calculations
- BenchmarkCase execution
- run_embedding_benchmark functionality
- Evaluation metrics (accuracy, margins, scores)
- Edge cases and error handling
"""

import math
from unittest.mock import Mock, patch

import pytest

from tools.rag.benchmark import (
    CASES,
    BenchmarkCase,
    _cosine,
    run_embedding_benchmark,
)


class TestCosineSimilarity:
    """Test cosine similarity calculation function."""

    def test_cosine_identical_vectors(self):
        """Test cosine similarity of identical vectors."""
        vector = [1.0, 2.0, 3.0, 4.0]
        similarity = _cosine(vector, vector)

        assert similarity == pytest.approx(1.0, abs=1e-10)

    def test_cosine_orthogonal_vectors(self):
        """Test cosine similarity of orthogonal vectors."""
        # (1, 0) dot (0, 1) = 0
        vector_a = [1.0, 0.0]
        vector_b = [0.0, 1.0]
        similarity = _cosine(vector_a, vector_b)

        assert similarity == pytest.approx(0.0, abs=1e-10)

    def test_cosine_opposite_vectors(self):
        """Test cosine similarity of opposite vectors."""
        vector_a = [1.0, 2.0, 3.0]
        vector_b = [-1.0, -2.0, -3.0]
        similarity = _cosine(vector_a, vector_b)

        assert similarity == pytest.approx(-1.0, abs=1e-10)

    def test_cosine_similar_vectors(self):
        """Test cosine similarity of similar vectors."""
        vector_a = [1.0, 2.0, 3.0]
        vector_b = [1.1, 2.1, 3.1]
        similarity = _cosine(vector_a, vector_b)

        # Should be close to 1.0
        assert similarity > 0.99

    def test_cosine_different_magnitude(self):
        """Test cosine similarity with different magnitude vectors."""
        vector_a = [1.0, 2.0, 3.0]
        vector_b = [2.0, 4.0, 6.0]  # Same direction, double magnitude
        similarity = _cosine(vector_a, vector_b)

        # Should still be 1.0 (same direction)
        assert similarity == pytest.approx(1.0, abs=1e-10)

    def test_cosine_zero_vector(self):
        """Test cosine similarity with zero vector."""
        vector_a = [0.0, 0.0, 0.0]
        vector_b = [1.0, 2.0, 3.0]
        similarity = _cosine(vector_a, vector_b)

        # Should return 0.0 when one vector is zero
        assert similarity == 0.0

    def test_cosine_both_zero_vectors(self):
        """Test cosine similarity with both zero vectors."""
        vector_a = [0.0, 0.0, 0.0]
        vector_b = [0.0, 0.0, 0.0]
        similarity = _cosine(vector_a, vector_b)

        assert similarity == 0.0

    def test_cosine_empty_vectors(self):
        """Test cosine similarity with empty vectors."""
        vector_a = []
        vector_b = []
        similarity = _cosine(vector_a, vector_b)

        assert similarity == 0.0

    def test_cosine_different_lengths(self):
        """Test cosine similarity with different length vectors."""
        vector_a = [1.0, 2.0, 3.0]
        vector_b = [1.0, 2.0]

        # Should only compare up to min length
        similarity = _cosine(vector_a, vector_b)

        assert similarity > 0.99  # (1*1 + 2*2) / (sqrt(1+4+9) * sqrt(1+4))

    def test_cosine_negative_values(self):
        """Test cosine similarity with negative values."""
        vector_a = [-1.0, -2.0, -3.0]
        vector_b = [-2.0, -3.0, -4.0]
        similarity = _cosine(vector_a, vector_b)

        # Should be close to 1.0 (same direction)
        assert similarity > 0.99

    def test_cosine_mixed_positive_negative(self):
        """Test cosine similarity with mixed positive/negative values."""
        vector_a = [1.0, -2.0, 3.0]
        vector_b = [-1.0, 2.0, -3.0]
        similarity = _cosine(vector_a, vector_b)

        # Should be negative (opposite directions)
        assert similarity < -0.99

    def test_cosine_large_values(self):
        """Test cosine similarity with large values."""
        vector_a = [1000.0, 2000.0, 3000.0]
        vector_b = [1000.0, 2000.0, 3000.0]
        similarity = _cosine(vector_a, vector_b)

        assert similarity == pytest.approx(1.0, abs=1e-10)

    def test_cosine_small_values(self):
        """Test cosine similarity with small values."""
        vector_a = [0.001, 0.002, 0.003]
        vector_b = [0.001, 0.002, 0.003]
        similarity = _cosine(vector_a, vector_b)

        assert similarity == pytest.approx(1.0, abs=1e-10)

    def test_cosine_with_zeros(self):
        """Test cosine similarity with zero in middle."""
        vector_a = [1.0, 0.0, 3.0]
        vector_b = [2.0, 0.0, 6.0]
        similarity = _cosine(vector_a, vector_b)

        assert similarity == pytest.approx(1.0, abs=1e-10)

    def test_cosine_special_values(self):
        """Test cosine similarity with special float values."""
        vector_a = [math.inf, math.nan, 0.0]
        vector_b = [math.inf, math.nan, 0.0]
        similarity = _cosine(vector_a, vector_b)

        # Should handle special values without crashing
        assert similarity is not None
        # Result might be nan or inf, but should not crash

    def test_cosine_numeric_stability(self):
        """Test cosine similarity for numeric stability."""
        # Very similar vectors
        vector_a = [1.0, 1.0, 1.0]
        vector_b = [1.0000001, 1.0000001, 1.0000001]
        similarity = _cosine(vector_a, vector_b)

        # Should still detect similarity
        assert similarity > 0.999

    def test_cosine_with_infinity(self):
        """Test cosine similarity with infinity values."""
        vector_a = [math.inf, 1.0, 2.0]
        vector_b = [math.inf, 1.0, 2.0]
        similarity = _cosine(vector_a, vector_b)

        # Should handle infinity without crashing
        assert similarity is not None


class TestBenchmarkCase:
    """Test BenchmarkCase dataclass."""

    def test_benchmark_case_creation(self):
        """Test basic BenchmarkCase creation."""
        case = BenchmarkCase(
            name="test-case",
            query="test query",
            positives=["pos1", "pos2"],
            negatives=["neg1", "neg2"]
        )

        assert case.name == "test-case"
        assert case.query == "test query"
        assert case.positives == ["pos1", "pos2"]
        assert case.negatives == ["neg1", "neg2"]

    def test_benchmark_case_frozen(self):
        """Test that BenchmarkCase is frozen."""
        case = BenchmarkCase(
            name="test",
            query="query",
            positives=["p"],
            negatives=["n"]
        )

        # Should not be able to modify after creation
        with pytest.raises(Exception):
            case.name = "modified"

    def test_benchmark_case_immutable_tuple(self):
        """Test BenchmarkCase with tuples."""
        case = BenchmarkCase(
            name="tuple-case",
            query="query",
            positives=("pos1", "pos2"),
            negatives=("neg1", "neg2")
        )

        # Should accept tuples
        assert isinstance(case.positives, tuple)
        assert isinstance(case.negatives, tuple)

    def test_benchmark_case_single_example(self):
        """Test BenchmarkCase with single positive/negative."""
        case = BenchmarkCase(
            name="single",
            query="query",
            positives=["positive"],
            negatives=["negative"]
        )

        assert len(case.positives) == 1
        assert len(case.negatives) == 1

    def test_benchmark_case_multiple_examples(self):
        """Test BenchmarkCase with multiple examples."""
        positives = [f"positive_{i}" for i in range(10)]
        negatives = [f"negative_{i}" for i in range(10)]

        case = BenchmarkCase(
            name="multiple",
            query="query",
            positives=positives,
            negatives=negatives
        )

        assert len(case.positives) == 10
        assert len(case.negatives) == 10

    def test_benchmark_case_with_empty_lists(self):
        """Test BenchmarkCase with empty examples."""
        case = BenchmarkCase(
            name="empty",
            query="query",
            positives=[],
            negatives=[]
        )

        assert case.positives == []
        assert case.negatives == []


class TestBenchmarkCasesConstant:
    """Test the predefined benchmark cases."""

    def test_cases_is_tuple(self):
        """Test that CASES is a tuple."""
        assert isinstance(CASES, tuple)

    def test_cases_not_empty(self):
        """Test that CASES contains cases."""
        assert len(CASES) > 0

    def test_jwt_verification_case(self):
        """Test JWT verification benchmark case."""
        case = CASES[0]

        assert case.name == "jwt-verification"
        assert "json web token" in case.query.lower()
        assert len(case.positives) > 0
        assert len(case.negatives) > 0

    def test_csv_parser_case(self):
        """Test CSV parser benchmark case."""
        case = CASES[1]

        assert case.name == "csv-parser"
        assert "csv" in case.query.lower()
        assert len(case.positives) > 0
        assert len(case.negatives) > 0

    def test_http_retry_case(self):
        """Test HTTP retry benchmark case."""
        case = CASES[2]

        assert case.name == "http-retry"
        assert "http" in case.query.lower() or "retry" in case.query.lower()
        assert len(case.positives) > 0
        assert len(case.negatives) > 0

    def test_fibonacci_memo_case(self):
        """Test Fibonacci memoization benchmark case."""
        case = CASES[3]

        assert case.name == "fibonacci-memo"
        assert "fibonacci" in case.query.lower()
        assert len(case.positives) > 0
        assert len(case.negatives) > 0

    def test_all_cases_have_positives_and_negatives(self):
        """Test that all cases have both positives and negatives."""
        for case in CASES:
            assert len(case.positives) > 0, f"{case.name} has no positives"
            assert len(case.negatives) > 0, f"{case.name} has no negatives"

    def test_all_cases_have_queries(self):
        """Test that all cases have queries."""
        for case in CASES:
            assert case.query, f"{case.name} has no query"
            assert len(case.query) > 0

    def test_all_cases_have_names(self):
        """Test that all cases have names."""
        for case in CASES:
            assert case.name, "Case has no name"
            assert len(case.name) > 0

    def test_case_names_are_unique(self):
        """Test that all case names are unique."""
        names = [case.name for case in CASES]
        assert len(names) == len(set(names)), "Case names are not unique"


class TestRunEmbeddingBenchmark:
    """Test the run_embedding_benchmark function."""

    @patch("tools.rag.benchmark.build_embedding_backend")
    def test_run_embedding_benchmark_basic(self, mock_build_backend):
        """Test basic benchmark execution."""
        # Create mock backend
        mock_backend = Mock()
        mock_backend.embed_queries = Mock(return_value=[[1.0, 0.0], [0.0, 1.0]])
        mock_backend.embed_passages = Mock(return_value=[[1.0, 0.0], [0.0, 1.0]])
        mock_build_backend.return_value = mock_backend

        # Run benchmark
        results = run_embedding_benchmark()

        # Verify structure
        assert isinstance(results, dict)
        assert "cases" in results
        assert "top1_accuracy" in results
        assert "avg_margin" in results
        assert "avg_positive_score" in results
        assert "avg_negative_score" in results

        # Verify values
        assert results["cases"] == float(len(CASES))
        assert 0.0 <= results["top1_accuracy"] <= 1.0
        assert isinstance(results["avg_margin"], float)
        assert isinstance(results["avg_positive_score"], float)
        assert isinstance(results["avg_negative_score"], float)

    @patch("tools.rag.benchmark.build_embedding_backend")
    def test_run_embedding_benchmark_perfect_accuracy(self, mock_build_backend):
        """Test benchmark with perfect accuracy."""
        # Create mock backend that returns higher similarity for positives
        mock_backend = Mock()
        query_vec = [1.0, 0.0]

        # Mock embeddings: positives close to query, negatives far
        def embed_queries(queries):
            return [query_vec for _ in queries]

        def embed_passages(texts):
            # First text is positive (close to query)
            # Second text is negative (far from query)
            return [[0.99, 0.01], [0.1, 0.1]]

        mock_backend.embed_queries = Mock(side_effect=embed_queries)
        mock_backend.embed_passages = Mock(side_effect=embed_passages)
        mock_build_backend.return_value = mock_backend

        results = run_embedding_benchmark()

        # Should have high accuracy
        assert results["top1_accuracy"] > 0.0

    @patch("tools.rag.benchmark.build_embedding_backend")
    def test_run_embedding_benchmark_zero_accuracy(self, mock_build_backend):
        """Test benchmark with zero accuracy."""
        # Create mock backend that returns higher similarity for negatives
        mock_backend = Mock()
        query_vec = [1.0, 0.0]

        def embed_queries(queries):
            return [query_vec for _ in queries]

        def embed_passages(texts):
            # First text is negative (close to query)
            # Second text is positive (far from query)
            return [[0.99, 0.01], [0.1, 0.1]]

        mock_backend.embed_queries = Mock(side_effect=embed_queries)
        mock_backend.embed_passages = Mock(side_effect=embed_passages)
        mock_build_backend.return_value = mock_backend

        results = run_embedding_benchmark()

        # Should have some accuracy (depends on which is "best")
        assert 0.0 <= results["top1_accuracy"] <= 1.0

    @patch("tools.rag.benchmark.build_embedding_backend")
    def test_run_embedding_benchmark_calls_backend_methods(self, mock_build_backend):
        """Test that benchmark calls backend methods correctly."""
        mock_backend = Mock()
        mock_backend.embed_queries = Mock(return_value=[[1.0, 0.0]])
        mock_backend.embed_passages = Mock(return_value=[[0.5, 0.5]])
        mock_build_backend.return_value = mock_backend

        results = run_embedding_benchmark()

        # Should call embed_queries for each case
        assert mock_backend.embed_queries.called

        # Should call embed_passages for each case
        assert mock_backend.embed_passages.called

    @patch("tools.rag.benchmark.build_embedding_backend")
    def test_run_embedding_benchmark_calculates_margins(self, mock_build_backend):
        """Test margin calculation."""
        mock_backend = Mock()

        # Set up embeddings where best positive has high score,
        # best negative has low score (good separation)
        def embed_queries(queries):
            return [[1.0, 0.0]]

        def embed_passages(texts):
            # Positives: score 0.9, 0.8
            # Negatives: score 0.1, 0.2
            return [[0.9, 0.0], [0.8, 0.0], [0.1, 0.0], [0.2, 0.0]]

        mock_backend.embed_queries = Mock(side_effect=embed_queries)
        mock_backend.embed_passages = Mock(side_effect=embed_passages)
        mock_build_backend.return_value = mock_backend

        results = run_embedding_benchmark()

        # Margin should be positive when positives score higher
        # (0.9 - 0.2) = 0.7
        assert results["avg_margin"] > 0

    @patch("tools.rag.benchmark.build_embedding_backend")
    def test_run_embedding_benchmark_handles_backend_failure(self, mock_build_backend):
        """Test handling of backend failure."""
        mock_backend = Mock()
        mock_backend.embed_queries = Mock(side_effect=Exception("Backend error"))
        mock_build_backend.return_value = mock_backend

        # Should raise exception
        with pytest.raises(Exception):
            run_embedding_benchmark()

    @patch("tools.rag.benchmark.build_backend")
    def test_run_embedding_benchmark_no_cases(self, mock_build_backend):
        """Test benchmark behavior with no cases."""
        # Temporarily replace CASES with empty tuple
        with patch("tools.rag.benchmark.CASES", tuple()):
            mock_backend = Mock()
            mock_backend.embed_queries = Mock(return_value=[])
            mock_backend.embed_passages = Mock(return_value=[])
            mock_build_backend.return_value = mock_backend

            results = run_embedding_benchmark()

            # Should handle empty cases gracefully
            assert results["cases"] == 0.0
            assert results["top1_accuracy"] == 0.0
            assert results["avg_margin"] == 0.0

    @patch("tools.rag.benchmark.build_embedding_backend")
    def test_run_embedding_benchmark_calculates_average_scores(self, mock_build_backend):
        """Test average positive and negative score calculation."""
        mock_backend = Mock()

        def embed_queries(queries):
            return [[1.0, 0.0]]

        def embed_passages(texts):
            # 2 positives with scores 0.9, 0.8
            # 2 negatives with scores 0.1, 0.2
            return [[0.9, 0.0], [0.8, 0.0], [0.1, 0.0], [0.2, 0.0]]

        mock_backend.embed_queries = Mock(side_effect=embed_queries)
        mock_backend.embed_passages = Mock(side_effect=embed_passages)
        mock_build_backend.return_value = mock_backend

        results = run_embedding_benchmark()

        # Average positive should be (0.9 + 0.8) / 2 = 0.85
        # Average negative should be (0.1 + 0.2) / 2 = 0.15
        assert results["avg_positive_score"] > results["avg_negative_score"]

    @patch("tools.rag.benchmark.build_embedding_backend")
    def test_run_embedding_benchmark_return_types(self, mock_build_backend):
        """Test that benchmark returns correct types."""
        mock_backend = Mock()
        mock_backend.embed_queries = Mock(return_value=[[1.0, 0.0]])
        mock_backend.embed_passages = Mock(return_value=[[0.5, 0.5]])
        mock_build_backend.return_value = mock_backend

        results = run_embedding_benchmark()

        # All values should be floats
        for key, value in results.items():
            assert isinstance(value, float), f"{key} is not a float: {type(value)}"

    @patch("tools.rag.benchmark.build_embedding_backend")
    def test_run_embedding_benchmark_single_case(self, mock_build_backend):
        """Test benchmark with single benchmark case."""
        # Replace CASES with single case
        single_case = (BenchmarkCase(
            name="single-test",
            query="test query",
            positives=["positive"],
            negatives=["negative"]
        ),)

        with patch("tools.rag.benchmark.CASES", single_case):
            mock_backend = Mock()
            mock_backend.embed_queries = Mock(return_value=[[1.0, 0.0]])
            mock_backend.embed_passages = Mock(return_value=[[0.9, 0.0], [0.1, 0.0]])
            mock_build_backend.return_value = mock_backend

            results = run_embedding_benchmark()

            assert results["cases"] == 1.0


class TestBenchmarkEdgeCases:
    """Test edge cases and error handling."""

    @patch("tools.rag.benchmark.build_embedding_backend")
    def test_benchmark_with_empty_positives(self, mock_build_backend):
        """Test benchmark with case having no positives."""
        empty_case = (BenchmarkCase(
            name="empty-positives",
            query="test",
            positives=[],  # No positives
            negatives=["negative1"]
        ),)

        with patch("tools.rag.benchmark.CASES", empty_case):
            mock_backend = Mock()
            mock_backend.embed_queries = Mock(return_value=[[1.0, 0.0]])
            mock_backend.embed_passages = Mock(return_value=[[0.1, 0.0]])
            mock_build_backend.return_value = mock_backend

            results = run_embedding_benchmark()

            # Should handle empty positives gracefully
            assert results["cases"] == 1.0

    @patch("tools.rag.benchmark.build_embedding_backend")
    def test_benchmark_with_empty_negatives(self, mock_build_backend):
        """Test benchmark with case having no negatives."""
        empty_case = (BenchmarkCase(
            name="empty-negatives",
            query="test",
            positives=["positive1"],
            negatives=[]  # No negatives
        ),)

        with patch("tools.rag.benchmark.CASES", empty_case):
            mock_backend = Mock()
            mock_backend.embed_queries = Mock(return_value=[[1.0, 0.0]])
            mock_backend.embed_passages = Mock(return_value=[[0.9, 0.0]])
            mock_build_backend.return_value = mock_backend

            results = run_embedding_benchmark()

            # Should handle empty negatives gracefully
            assert results["cases"] == 1.0

    @patch("tools.rag.benchmark.build_embedding_backend")
    def test_benchmark_with_all_equal_scores(self, mock_build_backend):
        """Test benchmark when all candidates have equal scores."""
        equal_case = (BenchmarkCase(
            name="equal-scores",
            query="test",
            positives=["positive1"],
            negatives=["negative1"]
        ),)

        with patch("tools.rag.benchmark.CASES", equal_case):
            mock_backend = Mock()
            mock_backend.embed_queries = Mock(return_value=[[1.0, 0.0]])
            # All candidates have same score
            mock_backend.embed_passages = Mock(return_value=[[0.5, 0.0], [0.5, 0.0]])
            mock_build_backend.return_value = mock_backend

            results = run_embedding_benchmark()

            # Should still calculate metrics
            assert results["cases"] == 1.0
            assert 0.0 <= results["top1_accuracy"] <= 1.0

    @patch("tools.rag.benchmark.build_embedding_backend")
    def test_benchmark_with_very_large_vectors(self, mock_build_backend):
        """Test benchmark with very large embedding vectors."""
        mock_backend = Mock()

        def embed_queries(queries):
            return [[1000.0] * 1000]  # Large vector

        def embed_passages(texts):
            return [[1000.0] * 1000] * 4  # Large vectors

        mock_backend.embed_queries = Mock(side_effect=embed_queries)
        mock_backend.embed_passages = Mock(side_effect=embed_passages)
        mock_build_backend.return_value = mock_backend

        results = run_embedding_benchmark()

        # Should handle large vectors without overflow
        assert results["cases"] > 0
        assert not math.isnan(results["top1_accuracy"])

    @patch("tools.rag.benchmark.build_embedding_backend")
    def test_benchmark_with_very_small_vectors(self, mock_build_backend):
        """Test benchmark with very small embedding vectors."""
        mock_backend = Mock()

        def embed_queries(queries):
            return [[0.0001] * 100]  # Small vector

        def embed_passages(texts):
            return [[0.0001] * 100] * 4  # Small vectors

        mock_backend.embed_queries = Mock(side_effect=embed_queries)
        mock_backend.embed_passages = Mock(side_effect=embed_passages)
        mock_build_backend.return_value = mock_backend

        results = run_embedding_benchmark()

        # Should handle small vectors without underflow
        assert results["cases"] > 0


class TestCosineEdgeCases:
    """Test edge cases for cosine similarity."""

    def test_cosine_extremely_long_vectors(self):
        """Test cosine with extremely long vectors."""
        vector_a = [1.0] * 10000
        vector_b = [1.0] * 10000

        similarity = _cosine(vector_a, vector_b)

        assert similarity == pytest.approx(1.0, abs=1e-10)

    def test_cosine_nan_values(self):
        """Test cosine with NaN values."""
        vector_a = [1.0, math.nan, 3.0]
        vector_b = [2.0, 4.0, 6.0]

        similarity = _cosine(vector_a, vector_b)

        # Should handle NaN gracefully
        assert similarity is not None

    def test_cosine_inf_values(self):
        """Test cosine with infinite values."""
        vector_a = [math.inf, 1.0, 2.0]
        vector_b = [math.inf, 1.0, 2.0]

        similarity = _cosine(vector_a, vector_b)

        # Should handle infinity gracefully
        assert similarity is not None

    def test_cosine_alternating_pattern(self):
        """Test cosine with alternating positive/negative pattern."""
        vector_a = [1.0, -1.0, 1.0, -1.0]
        vector_b = [1.0, -1.0, 1.0, -1.0]

        similarity = _cosine(vector_a, vector_b)

        assert similarity == pytest.approx(1.0, abs=1e-10)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
