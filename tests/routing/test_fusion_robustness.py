from llmc.routing.fusion import fuse_scores

def test_fusion_relative_vs_absolute_quality():
    """
    Gap: MinMax normalization destroys absolute score differences between routes.
    
    Route A (Good): [0.9, 0.8] -> Norm: [1.0, 0.0]
    Route B (Bad):  [0.2, 0.1] -> Norm: [1.0, 0.0]
    
    Fused (50/50 weights):
    A_top: 0.5
    B_top: 0.5
    
    Realistically, A_top (0.9) should CRUSH B_top (0.2).
    """
    route_results = {
        "good_route": [
            {"slice_id": "good_1", "score": 0.9},
            {"slice_id": "good_2", "score": 0.8},
        ],
        "bad_route": [
            {"slice_id": "bad_1", "score": 0.2},
            {"slice_id": "bad_2", "score": 0.1},
        ]
    }
    
    weights = {"good_route": 0.5, "bad_route": 0.5}
    
    fused = fuse_scores(route_results, weights)
    
    # Sort check: We expect good_1 and good_2 to be at the top.
    # Currently, bad_1 (score 0.2 -> norm 1.0 -> fused 0.5) ties with good_1.
    # And bad_1 beats good_2 (score 0.8 -> norm 0.0 -> fused 0.0).
    
    top_ids = [item["slice_id"] for item in fused]
    
    # The Gap: "bad_1" should NOT be above "good_2"
    # But with current logic, it is.
    
    # We assert the DESIRED behavior (which will fail)
    # This proves the gap exists.
    assert "good_2" in top_ids[:2], f"Expected good_2 to be in top 2, but got: {top_ids}"
    
    # Optional: asserting strictly that good_2 > bad_1
    good_2_score = next(x["score"] for x in fused if x["slice_id"] == "good_2")
    bad_1_score = next(x["score"] for x in fused if x["slice_id"] == "bad_1")
    
    assert good_2_score > bad_1_score, f"Good item (0.8) scored {good_2_score} vs Bad item (0.2) scored {bad_1_score}"
