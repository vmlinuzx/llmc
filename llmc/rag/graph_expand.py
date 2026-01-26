"""
Graph Expansion for RAG candidates using 1-hop neighbor lookups.
"""
from __future__ import annotations

import logging
from typing import Any

from .graph_index import GraphIndices, GraphNotFound, load_indices

logger = logging.getLogger(__name__)

class GraphExpander:
    """
    Expands a set of retrieval candidates by adding their 1-hop graph neighbors.
    """
    def __init__(
        self,
        indices: GraphIndices,
        decay_factor: float = 0.4,
        top_n_expand: int = 5,
        max_neighbors_per: int = 3,
        hub_threshold: int = 50,
    ):
        self.indices = indices
        self.decay_factor = decay_factor
        self.top_n_expand = top_n_expand
        self.max_neighbors_per = max_neighbors_per
        self.hub_threshold = hub_threshold

    def expand_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Add graph neighbors to the candidate list.
        """
        if not candidates:
            return []

        expanded = list(candidates)
        # Normalize paths in seen_paths to avoid duplicates if keys vary
        # candidates usually have 'file_path' from _score_candidates -> SpanSearchResult conversion
        seen_paths = set()
        for c in candidates:
            p = c.get("file_path") or c.get("path")
            if p:
                seen_paths.add(str(p))
        
        candidates_to_expand = candidates[:self.top_n_expand]
        
        for cand in candidates_to_expand:
            symbol = cand.get("symbol")
            if not symbol:
                continue
                
            # Fetch neighbors
            neighbors = set()
            
            # Upstream (where-used)
            if symbol in self.indices.symbol_to_files:
                upstream = self.indices.symbol_to_files[symbol]
                neighbors.update(upstream)
                
            # Downstream (callees)
            if symbol in self.indices.symbol_to_callee_files:
                downstream = self.indices.symbol_to_callee_files[symbol]
                neighbors.update(downstream)
            
            # Hub penalty
            if len(neighbors) > self.hub_threshold:
                logger.debug(f"Skipping graph expansion for hub node {symbol} (degree {len(neighbors)})")
                continue
                
            # Limit neighbors
            sorted_neighbors = sorted(list(neighbors))[:self.max_neighbors_per]
            
            base_score = cand.get("score", 0.0)
            neighbor_score = base_score * self.decay_factor
            
            for path in sorted_neighbors:
                path_str = str(path)
                if path_str in seen_paths:
                    continue
                
                # Create neighbor candidate
                # We construct a minimal valid dict compatible with SpanSearchResult reconstruction
                neighbor = {
                    "file_path": path_str,
                    "path": path_str, # Redundant but safe
                    "symbol": "", # Unknown symbol for the file
                    "kind": "file",
                    "start_line": 0,
                    "end_line": 0,
                    "score": neighbor_score,
                    "summary": f"Graph neighbor of {symbol}",
                    "span_hash": f"graph_{hash(path_str)}", # Fake hash
                    "_expansion_source": cand.get("file_path") or cand.get("path"),
                    "_expansion_type": "graph_neighbor"
                }
                
                expanded.append(neighbor)
                seen_paths.add(path_str)
                
        return expanded

def expand_with_graph(
    candidates: list[dict[str, Any]], 
    repo_root: Any, 
    config: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Convenience function to load graph and expand candidates.
    """
    graph_config = config.get("rag", {}).get("graph", {})
    if not graph_config.get("enable_expansion", False):
        return candidates

    try:
        indices = load_indices(repo_root)
    except (GraphNotFound, Exception):
        logger.debug("Graph indices not available, skipping expansion")
        return candidates

    expander = GraphExpander(
        indices=indices,
        decay_factor=graph_config.get("neighbor_score_factor", 0.4),
        top_n_expand=graph_config.get("top_n_expand", 5),
        max_neighbors_per=graph_config.get("max_neighbors_per", 3),
        hub_threshold=graph_config.get("hub_penalty_threshold", 50),
    )

    return expander.expand_candidates(candidates)
