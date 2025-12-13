def mean_reciprocal_rank(results: list[list[bool]]) -> float:
    """Calculate MRR across queries.

    Args:
        results: List of result lists, where True = relevant hit

    Returns:
        MRR score (0.0 to 1.0)
    """
    mrr = 0.0
    for result_list in results:
        for i, is_relevant in enumerate(result_list, 1):
            if is_relevant:
                mrr += 1.0 / i
                break
    return mrr / len(results) if results else 0.0


def recall_at_k(results: list[list[bool]], k: int = 10) -> float:
    """Calculate Recall@K across queries.

    Args:
        results: List of result lists, where True = relevant hit
        k: Number of results to consider

    Returns:
        Recall@K score (0.0 to 1.0)
    """
    hits = sum(1 for result_list in results if any(result_list[:k]))
    return hits / len(results) if results else 0.0
