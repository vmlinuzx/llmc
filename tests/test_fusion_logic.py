from llmc.routing.fusion import fuse_scores, normalize_scores


def test_normalize_scores_basic():
    results = [
        {"slice_id": "a", "score": 10.0},
        {"slice_id": "b", "score": 5.0},
        {"slice_id": "c", "score": 0.0},
    ]
    norm = normalize_scores(results)
    assert len(norm) == 3
    # Max is 10, min is 0. Range 10.
    # a: (10-0)/10 = 1.0
    # b: (5-0)/10 = 0.5
    # c: (0-0)/10 = 0.0

    assert norm[0]["_fusion_norm_score"] == 1.0
    assert norm[1]["_fusion_norm_score"] == 0.5
    assert norm[2]["_fusion_norm_score"] == 0.0


def test_normalize_scores_single_item():
    results = [{"slice_id": "a", "score": 5.0}]
    norm = normalize_scores(results)
    assert norm[0]["_fusion_norm_score"] == 1.0  # Default when max==min


def test_normalize_scores_all_same():
    results = [{"slice_id": "a", "score": 5.0}, {"slice_id": "b", "score": 5.0}]
    norm = normalize_scores(results)
    assert norm[0]["_fusion_norm_score"] == 1.0
    assert norm[1]["_fusion_norm_score"] == 1.0


def test_fuse_scores_single_route():
    # Should behave like normalized * weight
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
    assert fused[0]["score"] == 1.0  # (1.0 norm * 1.0 weight)
    assert fused[1]["slice_id"] == "b"
    assert fused[1]["score"] == 0.0


def test_fuse_scores_multi_route_disjoint():
    # Two routes, different items
    route_results = {
        "r1": [
            {"slice_id": "a", "score": 10.0},
            {"slice_id": "b", "score": 0.0},
        ],  # a=1.0, b=0.0
        "r2": [
            {"slice_id": "c", "score": 100.0},
            {"slice_id": "d", "score": 50.0},
        ],  # c=1.0, d=0.0 (min is 50) -> (50-50)/(100-50)=0? Wait.
        # r2 min is 50. range 50.
        # c: (100-50)/50 = 1.0
        # d: (50-50)/50 = 0.0
    }
    route_weights = {"r1": 0.5, "r2": 0.8}

    fused = fuse_scores(route_results, route_weights)

    # Expected:
    # a: 1.0 * 0.5 = 0.5
    # b: 0.0 * 0.5 = 0.0
    # c: 1.0 * 0.8 = 0.8
    # d: 0.0 * 0.8 = 0.0

    # Order: c (0.8), a (0.5), b/d (0.0)
    assert fused[0]["slice_id"] == "c"
    assert fused[0]["score"] == 0.8
    assert fused[1]["slice_id"] == "a"
    assert fused[1]["score"] == 0.5


def test_fuse_scores_overlap_max_wins():
    # 'a' is in both routes
    route_results = {
        "r1": [{"slice_id": "a", "score": 10.0}],  # norm=1.0
        "r2": [{"slice_id": "a", "score": 5.0}, {"slice_id": "b", "score": 10.0}],
        # r2: b=10(1.0), a=5 -> (5-5)/(10-5) = 0.0?
        # Wait, if r2 has [5, 10], min=5, max=10, range=5.
        # a: (5-5)/5 = 0.0
        # b: (10-5)/5 = 1.0
    }

    # Weights: r1=0.5, r2=0.8
    route_weights = {"r1": 0.5, "r2": 0.8}

    # a from r1: 1.0 * 0.5 = 0.5
    # a from r2: 0.0 * 0.8 = 0.0
    # a fused: max(0.5, 0.0) = 0.5

    # b from r2: 1.0 * 0.8 = 0.8

    fused = fuse_scores(route_results, route_weights)

    assert len(fused) == 2
    # b should be first (0.8)
    assert fused[0]["slice_id"] == "b"
    assert fused[0]["score"] == 0.8

    # a should be second (0.5)
    assert fused[1]["slice_id"] == "a"
    assert fused[1]["score"] == 0.5
