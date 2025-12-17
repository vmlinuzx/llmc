import pytest
from llmc.rag.search.reranker import should_rerank, rerank_results
from llmc.rag.telemetry import get_counter, reset_counters, RERANKER_INVOCATIONS_TOTAL

def setup_function():
    reset_counters()

def test_should_rerank_parameter_lookup():
    assert should_rerank("parameter_lookup") is True

def test_should_rerank_configuration():
    assert should_rerank("configuration") is True

def test_should_rerank_general():
    assert should_rerank("general_question") is False

def test_rerank_increments_counter():
    results = ["res1", "res2"]
    rerank_results(results, "query", "parameter_lookup")
    assert get_counter(RERANKER_INVOCATIONS_TOTAL) == 1
    
    # Should not increment for non-rerank intent
    rerank_results(results, "query", "general")
    assert get_counter(RERANKER_INVOCATIONS_TOTAL) == 1
