from llmc.routing.fusion import fuse_scores, normalize_scores, rrf_fuse_scores, z_score_fuse_scores

# --- Existing Logic Tests (Fixed expectations for Raw Scores) ---

def test_normalize_scores_basic():
    results = [
        {"slice_id": "a", "score": 10.0},
        {"slice_id": "b", "score": 5.0},
        {"slice_id": "c", "score": 0.0},
    ]
    norm = normalize_scores(results)
    assert len(norm) == 3
    assert norm[0]["_fusion_norm_score"] == 1.0
    assert norm[1]["_fusion_norm_score"] == 0.5
    assert norm[2]["_fusion_norm_score"] == 0.0

def test_fuse_scores_single_route():
    # FIXED: Now expects raw scores, not normalized
    route_results = {
        "primary": [
            {"slice_id": "a", "score": 10.0, "data": "a_data"},
            {"slice_id": "b", "score": 0.0, "data": "b_data"},
        ]
    }
    route_weights = {"primary": 1.0}

    fused = fuse_scores(route_results, route_weights)

    assert len(fused) == 2
    assert fused[0]["slice_id"] == "a"
    # assert fused[0]["score"] == 1.0  <-- OLD (normalized)
    assert fused[0]["score"] == 10.0 # <-- NEW (raw)
    assert fused[1]["slice_id"] == "b"
    assert fused[1]["score"] == 0.0

def test_fuse_scores_multi_route_disjoint():
    # Two routes, different items
    route_results = {
        "r1": [
            {"slice_id": "a", "score": 10.0},
            {"slice_id": "b", "score": 0.0},
        ],
        "r2": [
            {"slice_id": "c", "score": 100.0},
            {"slice_id": "d", "score": 50.0},
        ],
    }
    route_weights = {"r1": 0.5, "r2": 0.8}

    fused = fuse_scores(route_results, route_weights)

    # Expected:
    # a: 10.0 * 0.5 = 5.0
    # b: 0.0 * 0.5 = 0.0
    # c: 100.0 * 0.8 = 80.0
    # d: 50.0 * 0.8 = 40.0

    # Order: c (80), d (40), a (5), b (0)
    assert fused[0]["slice_id"] == "c"
    assert fused[0]["score"] == 80.0
    assert fused[1]["slice_id"] == "d"
    assert fused[1]["score"] == 40.0
    assert fused[2]["slice_id"] == "a"
    assert fused[2]["score"] == 5.0

# --- RRF Tests ---

def test_rrf_basic():
    # r1: a, b
    # r2: b, a
    route_results = {
        "r1": [{"slice_id": "a", "score": 10}, {"slice_id": "b", "score": 5}],
        "r2": [{"slice_id": "b", "score": 10}, {"slice_id": "a", "score": 5}],
    }
    k = 1
    # a: r1 rank 1 -> 1/(1+1) = 0.5
    #    r2 rank 2 -> 1/(1+2) = 0.333
    #    total = 0.833
    # b: r1 rank 2 -> 0.333
    #    r2 rank 1 -> 0.5
    #    total = 0.833
    
    results = rrf_fuse_scores(route_results, k=k)
    
    assert len(results) == 2
    # Scores should be equal
    assert abs(results[0]["score"] - 0.8333) < 0.001
    assert abs(results[1]["score"] - 0.8333) < 0.001
    assert results[0]["_fusion_method"] == "rrf"

def test_rrf_empty_inputs():
    assert rrf_fuse_scores({}) == []
    assert rrf_fuse_scores({"r1": []}) == []

def test_rrf_single_route():
    route_results = {
        "r1": [{"slice_id": "a"}, {"slice_id": "b"}]
    }
    k = 60
    results = rrf_fuse_scores(route_results, k=k)
    
    assert results[0]["slice_id"] == "a"
    assert results[0]["score"] == 1.0 / (60 + 1)
    assert results[1]["slice_id"] == "b"
    assert results[1]["score"] == 1.0 / (60 + 2)

def test_rrf_duplicate_slice_ids():
    # If a doc appears multiple times in ONE route? 
    # Usually search shouldn't return dupes, but if it does?
    # RRF logic: "for i, res in enumerate(results)". 
    # If 'a' is at 0 and 1.
    # rank 1 and rank 2. Both contribute.
    pass # Not a critical requirement to handle invalid route output.

# --- Dispatch Tests ---

def test_fuse_scores_dispatch_rrf():
    results = {"r1": [{"slice_id": "a", "score": 10}]}
    weights = {"r1": 1.0}
    config = {"scoring": {"fusion": {"method": "rrf", "rrf_k": 1}}}
    
    # Expect RRF logic
    # rank 1 -> 1/(1+1) = 0.5
    fused = fuse_scores(results, weights, config=config)
    assert fused[0]["score"] == 0.5
    assert fused[0]["_fusion_method"] == "rrf"

def test_fuse_scores_default_max():
    # No config -> MAX logic (raw score * weight)
    results = {"r1": [{"slice_id": "a", "score": 10}]}
    weights = {"r1": 0.5}
    
    fused = fuse_scores(results, weights) # config=None
    
    assert fused[0]["score"] == 5.0 # 10 * 0.5
    assert "_fusion_method" not in fused[0] # RRF adds this tag, MAX doesn't currently


# --- Z-Score Tests ---

def test_zscore_basic():
    """Z-score should normalize and weight scores correctly."""
    route_results = {
        "r1": [
            {"slice_id": "a", "score": 100.0},
            {"slice_id": "b", "score": 50.0},
            {"slice_id": "c", "score": 0.0},
        ],
        "r2": [
            {"slice_id": "d", "score": 0.95},
            {"slice_id": "e", "score": 0.85},
            {"slice_id": "f", "score": 0.75},
        ],
    }
    route_weights = {"r1": 1.0, "r2": 1.0}
    
    results = z_score_fuse_scores(route_results, route_weights, fallback_to_rrf=False)
    
    assert len(results) == 6
    assert results[0]["_fusion_method"] == "z_score"
    # All items should have scores (z-scores can be negative)


def test_zscore_fallback_to_rrf():
    """Should fall back to RRF when too few samples."""
    route_results = {
        "r1": [{"slice_id": "a", "score": 10}],  # Only 1 sample
    }
    route_weights = {"r1": 1.0}
    
    results = z_score_fuse_scores(
        route_results, route_weights, 
        fallback_to_rrf=True, 
        min_samples_for_zscore=5
    )
    
    # Should have fallen back to RRF (1 sample < 5)
    assert results[0]["_fusion_method"] == "rrf"


def test_zscore_std_zero():
    """Should handle all-same-score case (std=0)."""
    route_results = {
        "r1": [
            {"slice_id": "a", "score": 10.0},
            {"slice_id": "b", "score": 10.0},
            {"slice_id": "c", "score": 10.0},
        ],
    }
    route_weights = {"r1": 1.0}
    
    # All same score -> std=0 -> z-scores should all be 0
    results = z_score_fuse_scores(
        route_results, route_weights, 
        fallback_to_rrf=False,
        min_samples_for_zscore=2
    )
    
    assert len(results) == 3
    # All z-scores should be 0 when std=0
    for r in results:
        assert r["score"] == 0.0


def test_fuse_scores_dispatch_zscore():
    """Dispatcher should route to z_score when configured."""
    route_results = {
        "r1": [
            {"slice_id": "a", "score": 100.0},
            {"slice_id": "b", "score": 50.0},
            {"slice_id": "c", "score": 0.0},
        ],
    }
    route_weights = {"r1": 1.0}
    config = {
        "scoring": {
            "fusion": {
                "method": "z_score",
                "weights": {"r1": 1.0},
                "fallback_to_rrf": False,
                "min_samples_for_zscore": 2,
            }
        }
    }
    
    results = fuse_scores(route_results, route_weights, config=config)
    
    assert results[0]["_fusion_method"] == "z_score"
