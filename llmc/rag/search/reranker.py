from llmc.rag.telemetry import RERANKER_INVOCATIONS_TOTAL, increment_counter

RERANK_INTENTS = {"parameter_lookup", "configuration"}


def should_rerank(query_intent: str) -> bool:
    """Return True if query intent should trigger reranking."""
    return query_intent in RERANK_INTENTS


def rerank_results(results: list, query: str, intent: str) -> list:
    """Rerank results if intent qualifies. Returns original list if not."""
    if not should_rerank(intent):
        return results
    # Stub: actual reranking with bge-reranker-v2-m3 deferred
    # For now, just return as-is but log the invocation
    increment_counter(RERANKER_INVOCATIONS_TOTAL)
    return results  # Placeholder
