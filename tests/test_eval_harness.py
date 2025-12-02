import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.rag.eval.routing_eval import evaluate_routing
from tools.rag.search import SpanSearchResult


@pytest.fixture
def mock_dataset(tmp_path):
    data = [
        {"id": "q1", "query": "code query", "expected_route": "code", "relevant_slice_ids": ["slice_1"]},
        {"id": "q2", "query": "docs query", "expected_route": "docs", "relevant_slice_ids": ["slice_2"]},
    ]
    p = tmp_path / "eval.jsonl"
    with open(p, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")
    return p

@patch("tools.rag.eval.routing_eval.load_config")
@patch("tools.rag.eval.routing_eval.find_repo_root")
@patch("tools.rag.eval.routing_eval.search_spans")
@patch("tools.rag.eval.routing_eval.create_router")
def test_evaluate_routing(mock_create_router, mock_search, mock_find_root, mock_load_config, mock_dataset):
    # Setup Mocks
    mock_find_root.return_value = Path("/tmp/repo")
    mock_load_config.return_value = {}
    
    # Mock Router
    router_instance = MagicMock()
    def decide_side_effect(query, **kwargs):
        if "code" in query:
            return {"route_name": "code", "confidence": 0.9}
        return {"route_name": "docs", "confidence": 0.8}
    router_instance.decide_route.side_effect = decide_side_effect
    mock_create_router.return_value = router_instance
    
    # Mock Search (Retrieval)
    # q1 should hit slice_1 (correct)
    # q2 should hit slice_3 (incorrect)
    def search_side_effect(query, **kwargs):
        if "code" in query:
            return [SpanSearchResult(span_hash="slice_1", score=1.0, path=Path("a"), symbol="a", kind="a", start_line=1, end_line=2, summary="")]
        return [SpanSearchResult(span_hash="slice_3", score=1.0, path=Path("b"), symbol="b", kind="b", start_line=1, end_line=2, summary="")]
    mock_search.side_effect = search_side_effect
    
    # Run Eval
    metrics = evaluate_routing(mock_dataset)
    
    # Assertions
    # q1: route correct (code==code), retrieval correct (slice_1 in [slice_1])
    # q2: route correct (docs==docs), retrieval incorrect (slice_2 not in [slice_3])
    
    assert metrics["total_examples"] == 2
    assert metrics["routing_accuracy"] == 1.0 # Both routes correct
    assert metrics["retrieval_hit_at_k"] == 0.5 # 1 out of 2 correct
    assert metrics["retrieval_mrr"] == 0.5 # (1/1 + 0) / 2 = 0.5
