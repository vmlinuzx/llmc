# SDD: Fusion Logic - MinMax Normalization Destroys Signal

## 1. Gap Description
The `normalize_scores` function in `llmc/routing/fusion.py` uses Min-Max normalization to scale scores to [0, 1] based on the local minimum and maximum of the returned results for that specific route.

This approach fails to preserve the "absolute quality" of the results.
- **Scenario:**
  - Route A (High Confidence): Returns scores [0.90, 0.91].
    - Normalized: 0.90 -> 0.0, 0.91 -> 1.0.
  - Route B (Low Confidence): Returns scores [0.10, 0.11].
    - Normalized: 0.10 -> 0.0, 0.11 -> 1.0.
  - Weights: Equal (0.5 each).

- **Result:**
  - Route B's top item (raw 0.11) gets a fused score of 0.5.
  - Route A's bottom item (raw 0.90) gets a fused score of 0.0.
  - **The system ranks the 0.11 item HIGHER than the 0.90 item.**

This completely undermines the routing logic when combining providers of different quality or when one route returns universally poor results.

## 2. Target Location
`tests/routing/test_fusion_robustness.py`

## 3. Test Strategy
We need a test that demonstrates this failure.
1.  **Setup:** Create mock results for two routes as described in the scenario (High vs Low quality).
2.  **Execution:** Call `fuse_scores` with these results and equal weights.
3.  **Assertion:** Verify that the items from the High Quality route (even the lowest scoring one) are ranked higher than the items from the Low Quality route.
    - Currently, this assertion is expected to **FAIL**.
    - The test should explicitly document this failure as a gap.

## 4. Implementation Details
```python
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
```
