from dataclasses import dataclass
from typing import Any
import statistics


@dataclass
class SearchResult:
    slice_id: str
    score: float
    # We might need other fields to reconstruct the full result object later,
    # but for fusion we primarily care about ID and score.
    # However, the actual search returns dictionaries or objects.
    # Let's assume for this helper we work with the raw objects returned by search
    # and assume they have 'slice_id' and 'score' keys/attributes.
    # To be safe/generic, let's work with dictionaries for the input results.
    original_result: dict[str, Any]


def normalize_scores(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Normalize scores in the list of results to [0, 1] range using min-max normalization.
    Returns a new list of results with 'normalized_score' added.
    """
    if not results:
        return []

    scores = [r["score"] for r in results]
    min_score = min(scores)
    max_score = max(scores)

    # Avoid division by zero if all scores are the same
    if max_score == min_score:
        # If all scores are equal, normalized score is 1.0 (or 0.0? 1.0 preserves 'goodness')
        # Let's use 1.0 if it's non-zero, else 0.0.
        # Actually, if max == min, it doesn't matter for ranking within this route,
        # but it matters for relative weight against other routes.
        # If there is no variance, we can't distinguish. Let's default to 1.0 if score > 0 else 0.0.
        val = 1.0 if max_score > 0 else 0.0
        return [{**r, "_fusion_norm_score": val} for r in results]

    score_range = max_score - min_score

    normalized = []
    for r in results:
        norm_val = (r["score"] - min_score) / score_range
        normalized.append({**r, "_fusion_norm_score": norm_val})

    return normalized


def fuse_scores(
    route_results: dict[str, list[dict[str, Any]]],
    route_weights: dict[str, float],
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Fuse results from multiple routes.

    Args:
        route_results: Dict mapping route_name -> list of search result dicts.
                       Each result must have 'slice_id' and 'score'.
        route_weights: Dict mapping route_name -> weight (float).
        config: Optional configuration dict. If None, loads from llmc.core.load_config().

    Returns:
        List of fused result dicts, sorted by final_score descending.
        Each result will have 'score' updated to the fused score.
        Original metadata from the 'best' route result is preserved.
    """
    if config is None:
        try:
            from llmc.core import load_config
            config = load_config()
        except ImportError:
            config = {}

    fusion_config = config.get("scoring", {}).get("fusion", {}) if config else {}
    method = fusion_config.get("method", "max")

    if method == "rrf":
        rrf_k = fusion_config.get("rrf_k", 60)
        return rrf_fuse_scores(route_results, k=rrf_k)

    if method == "z_score":
        weights = fusion_config.get("weights", route_weights)
        fallback = fusion_config.get("fallback_to_rrf", True)
        min_samples = fusion_config.get("min_samples_for_zscore", 5)
        return z_score_fuse_scores(route_results, weights, fallback, min_samples)

    # NOTE: We use RAW scores instead of normalizing per-route.
    # The old approach normalized each route's scores to [0,1], which caused
    # the best doc and best code file to both become 1.0 - defeating the purpose
    # of our extension boosts. Raw scores are already on the same 0-100 scale
    # thanks to normalized_score, so we use those directly.

    # Map slice_id -> (best_score, best_result_object)
    merged_map: dict[str, tuple[float, dict[str, Any]]] = {}

    for route_name, results in route_results.items():
        weight = route_weights.get(route_name, 1.0)
        if weight == 0.0:
            continue

        for res in results:
            slice_id = res["slice_id"]
            # Use raw score, apply weight
            raw_score = res.get("normalized_score", res.get("score", 0)) or 0
            weighted_score = float(raw_score) * weight

            if slice_id in merged_map:
                current_best_score, current_best_obj = merged_map[slice_id]
                # Strategy: MAX score
                if weighted_score > current_best_score:
                    merged_map[slice_id] = (weighted_score, res)
            else:
                merged_map[slice_id] = (weighted_score, res)

    # Convert back to list and sort
    final_results = []
    for slice_id, (fused_score, res_obj) in merged_map.items():
        final_res = res_obj.copy()
        final_res["score"] = fused_score
        final_results.append(final_res)

    # Sort descending by fused score
    final_results.sort(key=lambda x: x["score"], reverse=True)

    return final_results


def z_score_fuse_scores(
    route_results: dict[str, list[dict[str, Any]]],
    route_weights: dict[str, float],
    fallback_to_rrf: bool = True,
    min_samples_for_zscore: int = 5,
) -> list[dict[str, Any]]:
    """
    Z-Score normalized weighted fusion.

    Each route's scores are normalized to z-scores (mean=0, std=1),
    then weighted and summed. This aligns different score distributions
    while preserving relative magnitude information.

    Falls back to RRF if sample size is too small for reliable statistics.
    """
    # Check if we have enough samples
    total_samples = sum(len(results) for results in route_results.values())
    if total_samples < min_samples_for_zscore:
        if fallback_to_rrf:
            return rrf_fuse_scores(route_results)
        # If not falling back, proceed anyway with caution

    # Normalize each route's scores to z-scores
    normalized_routes: dict[str, list[tuple[str, float, dict[str, Any]]]] = {}

    for route_name, results in route_results.items():
        if not results:
            continue

        scores = [r.get("score", 0) for r in results]
        
        if len(scores) < 2:
            # Can't compute std with single sample, use 0.0 as z-score
            z_scores = [0.0] * len(scores)
        else:
            mean = statistics.mean(scores)
            std = statistics.stdev(scores)

            if std == 0:
                # All same score - can't normalize, z = 0 for all
                z_scores = [0.0] * len(scores)
            else:
                z_scores = [(s - mean) / std for s in scores]

        normalized_routes[route_name] = [
            (r["slice_id"], z, r)
            for r, z in zip(results, z_scores)
        ]

    # Merge with weights
    merged: dict[str, tuple[float, dict[str, Any]]] = {}

    for route_name, normalized in normalized_routes.items():
        weight = route_weights.get(route_name, 1.0)

        for slice_id, z_score, result in normalized:
            weighted_z = z_score * weight

            if slice_id in merged:
                current_z, current_result = merged[slice_id]
                # Sum z-scores (linear combination)
                # Keep metadata from the result with higher weighted z
                if weighted_z > current_z:
                    merged[slice_id] = (current_z + weighted_z, result)
                else:
                    merged[slice_id] = (current_z + weighted_z, current_result)
            else:
                merged[slice_id] = (weighted_z, result)

    # Build final list
    final_results = []
    for slice_id, (final_z, result) in merged.items():
        r = result.copy()
        r["score"] = final_z
        r["_fusion_method"] = "z_score"
        final_results.append(r)

    final_results.sort(key=lambda x: x["score"], reverse=True)
    return final_results


def rrf_fuse_scores(
    route_results: dict[str, list[dict[str, Any]]],
    k: int = 60,
) -> list[dict[str, Any]]:
    """
    Fuse results using Reciprocal Rank Fusion (RRF).
    score = sum(1 / (k + rank)) for each document across routes.
    Rank is 1-based.
    """
    # Map slice_id -> score
    merged_scores: dict[str, float] = {}
    # Map slice_id -> best result object (to preserve metadata)
    # We'll prioritize the result from the "first" route where it appears,
    # or just keep the one with the highest individual RRF component?
    # Usually we just keep one. Let's keep the first one we see or overwrite.
    # Requirement: "Preserves original result metadata from best-scoring route result"
    # "best-scoring" in RRF context usually means best rank.
    # So if doc is rank 1 in r1 and rank 5 in r2, we keep r1's metadata.
    merged_objs: dict[str, tuple[int, dict[str, Any]]] = {}  # slice_id -> (best_rank, obj)

    for route_name, results in route_results.items():
        for i, res in enumerate(results):
            rank = i + 1
            slice_id = res["slice_id"]
            
            # RRF score contribution
            score_part = 1.0 / (k + rank)
            merged_scores[slice_id] = merged_scores.get(slice_id, 0.0) + score_part

            # Metadata preservation (lowest rank is best)
            if slice_id not in merged_objs or rank < merged_objs[slice_id][0]:
                merged_objs[slice_id] = (rank, res)

    # Build final list
    final_results = []
    for slice_id, final_score in merged_scores.items():
        _, original_res = merged_objs[slice_id]
        new_res = original_res.copy()
        new_res["score"] = final_score
        new_res["_fusion_method"] = "rrf"
        final_results.append(new_res)

    # Sort descending
    final_results.sort(key=lambda x: x["score"], reverse=True)
    return final_results
