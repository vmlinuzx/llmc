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


def ndcg_at_k(results: list[list[float]], k: int = 10) -> float:
    """Calculate nDCG@K across queries.

    Args:
        results: List of result lists, where value is relevance score (0.0 to 1.0+)
        k: Number of results to consider

    Returns:
        nDCG@K score (0.0 to 1.0)
    """
    import math

    def dcg(scores: list[float]) -> float:
        return sum(
            (2**score - 1) / math.log2(i + 2)
            for i, score in enumerate(scores[:k])
        )

    ndcg_sum = 0.0
    for scores in results:
        actual_dcg = dcg(scores)
        ideal_scores = sorted(scores, reverse=True)
        ideal_dcg = dcg(ideal_scores)
        
        if ideal_dcg > 0:
            ndcg_sum += actual_dcg / ideal_dcg
        else:
            ndcg_sum += 0.0

    return ndcg_sum / len(results) if results else 0.0