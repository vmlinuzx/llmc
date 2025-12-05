import math
import struct

import pytest

from tools.rag.search import _score_candidates


def _pack_vector(vec):
    return struct.pack(f"<{len(vec)}f", *vec)


def _norm(vec):
    return math.sqrt(sum(v * v for v in vec))


def test_score_normalization_basic():
    # Setup: 2D vectors for simplicity
    # Query: [1, 0]
    query_vec = [1.0, 0.0]
    query_norm = 1.0

    # Candidate 1: [1, 0] -> Cosine 1.0 -> Norm 100.0
    # Candidate 2: [0, 1] -> Cosine 0.0 -> Norm 0.0
    # Candidate 3: [0.707, 0.707] -> Cosine ~0.707 -> Norm ~70.7

    candidates = [
        {
            "vec": _pack_vector([1.0, 0.0]),
            "span_hash": "h1",
            "file_path": "data1.dat",
            "symbol": "s1",
            "kind": "def",
            "start_line": 1,
            "end_line": 10,
            "summary": "exact match",
        },
        {
            "vec": _pack_vector([0.0, 1.0]),
            "span_hash": "h2",
            "file_path": "data2.dat",
            "symbol": "s2",
            "kind": "def",
            "start_line": 1,
            "end_line": 10,
            "summary": "orthogonal",
        },
        {
            "vec": _pack_vector([0.70710678, 0.70710678]),
            "span_hash": "h3",
            "file_path": "data3.dat",
            "symbol": "s3",
            "kind": "def",
            "start_line": 1,
            "end_line": 10,
            "summary": "45 degrees",
        },
    ]

    results = _score_candidates(query_vec, query_norm, candidates)

    # Sort by score desc (default behavior of _score_candidates)
    assert len(results) == 3

    # Check Result 1 (Best)
    r1 = results[0]
    assert r1.span_hash == "h1"
    assert r1.score == pytest.approx(1.0, 0.001)
    assert hasattr(r1, "normalized_score"), "SpanSearchResult must have normalized_score"
    assert r1.normalized_score == pytest.approx(100.0, 0.1)

    # Check Result 2 (Middle)
    r2 = results[1]
    assert r2.span_hash == "h3"
    assert r2.score == pytest.approx(0.707, 0.001)
    assert r2.normalized_score == pytest.approx(70.7, 0.1)

    # Check Result 3 (Worst)
    r3 = results[2]
    assert r3.span_hash == "h2"
    assert r3.score == pytest.approx(0.0, 0.001)
    assert r3.normalized_score == pytest.approx(0.0, 0.1)


def test_score_normalization_clamping():
    # Test that filename boost doesn't exceed 100.0
    # Query: "test"
    # File: "test.py" -> Boost 0.20
    # Vector: Exact match (1.0)
    # Raw Score: 1.20
    # Normalized: Should be clamped to 100.0

    query_vec = [1.0, 0.0]
    query_norm = 1.0

    candidates = [
        {
            "vec": _pack_vector([1.0, 0.0]),
            "span_hash": "h_boost",
            "file_path": "test.py",  # Matches query "test"
            "symbol": "s_boost",
            "kind": "def",
            "start_line": 1,
            "end_line": 10,
            "summary": "boosted",
        }
    ]

    results = _score_candidates(query_vec, query_norm, candidates, query_text="test")

    assert len(results) == 1
    r = results[0]

    # Raw score should include boost
    assert r.score > 1.0
    # 1.0 (cosine) + 0.15 (stem match) - 0.08 (test penalty) = 1.07
    assert r.score == pytest.approx(1.07, 0.001)
    
    # Normalized score should be clamped
    assert r.normalized_score == 100.0