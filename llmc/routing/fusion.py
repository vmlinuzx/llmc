from dataclasses import dataclass
from typing import Any


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
    
    scores = [r['score'] for r in results]
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
        return [{**r, '_fusion_norm_score': val} for r in results]
        
    score_range = max_score - min_score
    
    normalized = []
    for r in results:
        norm_val = (r['score'] - min_score) / score_range
        normalized.append({**r, '_fusion_norm_score': norm_val})
        
    return normalized

def fuse_scores(
    route_results: dict[str, list[dict[str, Any]]], 
    route_weights: dict[str, float]
) -> list[dict[str, Any]]:
    """
    Fuse results from multiple routes.
    
    Args:
        route_results: Dict mapping route_name -> list of search result dicts.
                       Each result must have 'slice_id' and 'score'.
        route_weights: Dict mapping route_name -> weight (float).
        
    Returns:
        List of fused result dicts, sorted by final_score descending.
        Each result will have 'score' updated to the fused score.
        Original metadata from the 'best' route result is preserved.
    """
    
    # 1. Normalize scores per route
    normalized_results: dict[str, list[dict[str, Any]]] = {}
    for route_name, results in route_results.items():
        normalized_results[route_name] = normalize_scores(results)
        
    # 2. Apply weights and merge
    # Map slice_id -> (best_score, best_result_object)
    merged_map: dict[str, tuple[float, dict[str, Any]]] = {}
    
    for route_name, results in normalized_results.items():
        weight = route_weights.get(route_name, 0.0)
        if weight == 0.0:
            continue
            
        for res in results:
            slice_id = res['slice_id']
            # Calculate weighted score
            weighted_score = res['_fusion_norm_score'] * weight
            
            if slice_id in merged_map:
                current_best_score, current_best_obj = merged_map[slice_id]
                # Strategy: MAX score (as per requirements)
                if weighted_score > current_best_score:
                    # Update with new best score and object (in case different routes provide different metadata)
                    # We overwrite the object to prefer metadata from the higher scoring route?
                    # Or we just update the score. Usually preferred to keep the metadata from the 'winning' route.
                    merged_map[slice_id] = (weighted_score, res)
                # else: keep existing
            else:
                merged_map[slice_id] = (weighted_score, res)
                
    # 3. Convert back to list and sort
    final_results = []
    for slice_id, (fused_score, res_obj) in merged_map.items():
        # Create a copy to avoid mutating input
        final_res = res_obj.copy()
        # Remove the temporary _fusion_norm_score
        final_res.pop('_fusion_norm_score', None)
        # Update the main score to be the fused score
        final_res['score'] = fused_score
        # Add a debugging field to see where it came from/how it was calculated? 
        # Maybe later, for now keep it clean.
        final_results.append(final_res)
        
    # Sort descending
    final_results.sort(key=lambda x: x['score'], reverse=True)
    
    return final_results
