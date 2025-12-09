# Gap Analysis Report: Routing Fusion Logic

**Date:** 2025-12-08
**Agent:** Rem (Gap Analysis Demon)
**Topic:** Routing & Fusion Logic

## 1. Executive Summary
A critical logic gap was identified in the `llmc.routing.fusion` module. The current normalization strategy (Min-Max per route) destroys absolute score information, allowing low-quality results from one route to override high-quality results from another.

## 2. Identified Gaps

### Gap 1: Min-Max Normalization Distortion
- **Description:** The `normalize_scores` function scales results to [0, 1] based solely on the local minimum and maximum of that specific result set. This means a set of results `[0.1, 0.2]` is treated identically to `[0.9, 1.0]`.
- **Impact:** "Garbage In, Gold Out". A route returning poor matches can push them to the top of the fused list simply because they are the "best of the bad", displacing excellent matches from another route.
- **SDD:** [SDD-Routing-FusionNormalization.md](../SDDs/SDD-Routing-FusionNormalization.md)
- **Status:** **CONFIRMED**. The test `tests/routing/test_fusion_robustness.py` fails as predicted.

## 3. Technical Details
The failing test case (`test_fusion_relative_vs_absolute_quality`) demonstrates that an item with raw score `0.2` (from a bad route) ties with an item of score `0.9` (from a good route) and beats an item of score `0.8`.

```python
    # Expected good_2 (0.8) to be in top 2, but got: ['good_1', 'bad_1', 'good_2', 'bad_2']
```

## 4. Recommendations
1.  **Switch Fusion Algorithm:** Move from "Weighted Sum of Normalized Scores" to **Reciprocal Rank Fusion (RRF)**. RRF is robust to scale differences as it relies only on rank order ($1 / (k + rank)$).
2.  **Global Normalization:** If keeping score-based fusion, normalize across *all* candidates from all routes combined, not per-route.
3.  **Calibrated Scores:** Ensure upstream routers return calibrated probabilities (0-1) and skip normalization entirely if trusted.
