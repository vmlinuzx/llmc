from llmc.rag.telemetry import (
    ENRICHMENT_TRUNCATIONS_TOTAL,
    get_counter,
    increment_counter,
    reset_counters,
)


def setup_function():
    reset_counters()


def test_increment_counter():
    increment_counter(ENRICHMENT_TRUNCATIONS_TOTAL)
    assert get_counter(ENRICHMENT_TRUNCATIONS_TOTAL) == 1
    increment_counter(ENRICHMENT_TRUNCATIONS_TOTAL, 2)
    assert get_counter(ENRICHMENT_TRUNCATIONS_TOTAL) == 3


def test_get_counter_default():
    assert get_counter("unknown_counter") == 0


def test_reset_counters():
    increment_counter("test")
    reset_counters()
    assert get_counter("test") == 0
