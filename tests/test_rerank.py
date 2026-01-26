"""Tests for LLM-based setwise reranker."""
from llmc.rag.rerank import SetwiseReranker, rerank_with_llm


class MockLLMClient:
    """Mock LLM client for testing."""

    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def generate(self, prompt: str, temperature: float = 0) -> str:
        self.calls.append({"prompt": prompt, "temperature": temperature})
        return self.response


class TestSetwiseReranker:
    """Tests for SetwiseReranker class."""

    def test_rerank_no_candidates(self):
        """Should return empty list for empty input."""
        reranker = SetwiseReranker(llm_client=MockLLMClient('["1"]'))
        result = reranker.rerank("test query", [])
        assert result == []

    def test_rerank_no_llm_client(self):
        """Should return original candidates when no LLM client."""
        reranker = SetwiseReranker(llm_client=None)
        candidates = [
            {"slice_id": "a", "score": 0.9},
            {"slice_id": "b", "score": 0.8},
        ]
        result = reranker.rerank("test query", candidates)
        assert result == candidates

    def test_rerank_reorders_by_response(self):
        """Should reorder based on LLM selection."""
        client = MockLLMClient('["2", "1"]')  # Select 2nd, then 1st
        reranker = SetwiseReranker(llm_client=client, max_candidates=10)

        candidates = [
            {"slice_id": "a", "path": "a.py", "summary": "first"},
            {"slice_id": "b", "path": "b.py", "summary": "second"},
            {"slice_id": "c", "path": "c.py", "summary": "third"},
        ]

        result = reranker.rerank("test query", candidates)

        # Should be reordered: b, a, c
        assert result[0]["slice_id"] == "b"
        assert result[1]["slice_id"] == "a"
        assert result[2]["slice_id"] == "c"

    def test_rerank_handles_partial_selection(self):
        """Should include unselected candidates after selected ones."""
        client = MockLLMClient('["1"]')  # Only select first
        reranker = SetwiseReranker(llm_client=client)

        candidates = [
            {"slice_id": "a"},
            {"slice_id": "b"},
            {"slice_id": "c"},
        ]

        result = reranker.rerank("test", candidates)

        # First should be the selected one, rest in original order
        assert result[0]["slice_id"] == "a"
        assert len(result) == 3

    def test_rerank_handles_invalid_response(self):
        """Should fallback gracefully on invalid LLM response."""
        client = MockLLMClient("not valid json")
        reranker = SetwiseReranker(llm_client=client)

        candidates = [{"slice_id": "a"}, {"slice_id": "b"}]
        result = reranker.rerank("test", candidates)

        # Should still return candidates
        assert len(result) == 2

    def test_parse_response_valid(self):
        """Should parse valid JSON response."""
        reranker = SetwiseReranker()
        indices = reranker._parse_response('["1", "3", "2"]', 5)
        assert indices == [0, 2, 1]  # 0-indexed

    def test_parse_response_out_of_range(self):
        """Should filter out-of-range indices."""
        reranker = SetwiseReranker()
        indices = reranker._parse_response('["1", "10", "2"]', 3)
        assert 9 not in indices  # 10 is out of range

    def test_format_candidate(self):
        """Should format candidate correctly."""
        reranker = SetwiseReranker(max_snippet_chars=20)
        candidate = {
            "path": "/path/to/file.py",
            "symbol": "my_function",
            "summary": "This is a very long summary that should be truncated",
        }
        formatted = reranker._format_candidate(1, candidate)
        assert "[1]" in formatted
        assert "/path/to/file.py" in formatted
        assert "my_function" in formatted


class TestRerankWithLLM:
    """Tests for convenience function."""

    def test_disabled_by_default(self):
        """Should return original when no config."""
        candidates = [{"slice_id": "a"}]
        result = rerank_with_llm("test", candidates)
        assert result == candidates

    def test_disabled_in_config(self):
        """Should return original when disabled."""
        config = {"rag": {"rerank": {"enable_llm_rerank": False}}}
        candidates = [{"slice_id": "a"}]
        result = rerank_with_llm("test", candidates, config=config)
        assert result == candidates

    def test_short_query_skipped(self):
        """Should skip rerank for short queries."""
        config = {
            "rag": {
                "rerank": {
                    "enable_llm_rerank": True,
                    "min_query_length": 50,
                }
            }
        }
        candidates = [{"slice_id": "a"}]
        result = rerank_with_llm("short", candidates, config=config)
        assert result == candidates

    def test_enabled_with_client(self):
        """Should rerank when enabled with client."""
        config = {
            "rag": {
                "rerank": {
                    "enable_llm_rerank": True,
                    "min_query_length": 5,
                }
            }
        }
        client = MockLLMClient('["2", "1"]')
        candidates = [
            {"slice_id": "a"},
            {"slice_id": "b"},
        ]
        result = rerank_with_llm(
            "this is a longer query",
            candidates,
            config=config,
            llm_client=client,
        )
        # Should be reordered
        assert result[0]["slice_id"] == "b"
