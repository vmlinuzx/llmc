# Stub counters for enrichment telemetry
_counters = {}


def increment_counter(name: str, value: int = 1) -> None:
    """Increment a named counter."""
    _counters[name] = _counters.get(name, 0) + value


def get_counter(name: str) -> int:
    """Get current counter value."""
    return _counters.get(name, 0)


def reset_counters() -> None:
    """Reset all counters (for testing)."""
    _counters.clear()


# Predefined counter names
ENRICHMENT_TRUNCATIONS_TOTAL = "enrichment_truncations_total"
RERANKER_INVOCATIONS_TOTAL = "reranker_invocations_total"
