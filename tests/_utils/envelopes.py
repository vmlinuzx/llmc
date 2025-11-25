
from typing import Any


def assert_ok_envelope(res: Any) -> None:
    """Basic sanity checks for OK/FALLBACK envelopes."""
    assert hasattr(res, "meta")
    status = getattr(res.meta, "status", None)
    assert status in {"OK", "FALLBACK"}

    source = getattr(res, "source", getattr(res.meta, "source", None))
    assert source in {"RAG_GRAPH", "LOCAL_FALLBACK"}

    freshness = getattr(res, "freshness_state", getattr(res.meta, "freshness_state", "UNKNOWN"))
    assert freshness in {"FRESH", "STALE", "UNKNOWN"}


def assert_error_envelope(res: Any) -> None:
    """Basic sanity checks for ERROR envelopes."""
    assert hasattr(res, "meta")
    assert getattr(res.meta, "status", None) == "ERROR"
    assert getattr(res.meta, "error_code", None)
    assert getattr(res.meta, "message", None)

