from tools.rag.metrics.retrieval import mean_reciprocal_rank, recall_at_k


def test_mrr_first_position() -> None:
    """First result relevant = 1.0"""
    results = [[True, False, False]]
    assert mean_reciprocal_rank(results) == 1.0


def test_mrr_third_position() -> None:
    """Third result relevant = 0.333..."""
    results = [[False, False, True]]
    assert abs(mean_reciprocal_rank(results) - 0.333333) < 0.0001


def test_mrr_no_relevant() -> None:
    """No relevant results = 0.0"""
    results = [[False, False, False]]
    assert mean_reciprocal_rank(results) == 0.0


def test_mrr_mixed() -> None:
    """Mixed results"""
    results = [
        [True, False],  # 1.0
        [False, True],  # 0.5
        [False, False], # 0.0
    ]
    # (1.0 + 0.5 + 0.0) / 3 = 0.5
    assert mean_reciprocal_rank(results) == 0.5


def test_mrr_empty() -> None:
    """Empty results list"""
    assert mean_reciprocal_rank([]) == 0.0


def test_recall_at_10_all_hit() -> None:
    """All queries have hit = 1.0"""
    results = [[True] + [False] * 20] * 5
    assert recall_at_k(results, k=10) == 1.0


def test_recall_at_10_partial() -> None:
    """Some queries hit = correct ratio"""
    results = [
        [True] + [False] * 20,   # Hit at 1
        [False] * 20,            # Miss
    ]
    assert recall_at_k(results, k=10) == 0.5


def test_recall_at_10_miss_after_k() -> None:
    """Hit occurs after k"""
    # Hit is at index 10 (11th item), so Recall@10 should be 0.0
    results = [[False] * 10 + [True]]
    assert recall_at_k(results, k=10) == 0.0


def test_recall_at_k_empty() -> None:
    """Empty results list"""
    assert recall_at_k([], k=10) == 0.0
