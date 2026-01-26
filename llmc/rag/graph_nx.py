"""
NetworkX Adapter for LLMC RAG Graph.

This module demonstrates how to use NetworkX to replace manual graph traversals
and SQL recursive queries with standard graph algorithms.

It loads the legacy `rag_graph.json` artifact into a `networkx.DiGraph`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import networkx as nx

logger = logging.getLogger(__name__)


def load_graph_nx(repo_root: Path | str) -> nx.DiGraph:
    """
    Load the RAG graph into a NetworkX DiGraph.
    
    Nodes are keyed by their ID.
    Attributes (name, path, metadata) are stored as node data.
    Edges are directed, with 'type' stored as edge data.
    """
    repo_root = Path(repo_root)
    graph_path = repo_root / ".llmc" / "rag_graph.json"
    
    if not graph_path.exists():
        raise FileNotFoundError(f"Graph not found at {graph_path}")

    with open(graph_path, encoding="utf-8") as f:
        data = json.load(f)

    G = nx.DiGraph()

    # Extract nodes
    # Handle different schema variations seen in tool_handlers.py
    raw_nodes = data.get("nodes") or data.get("entities") or []
    for n in raw_nodes:
        nid = str(n.get("id") or n.get("nid") or n.get("name"))
        if not nid:
            continue
            
        # Store all attributes
        G.add_node(nid, **n)

    # Extract edges
    raw_edges = data.get("edges") or data.get("links") or data.get("relations") or []
    if not raw_edges:
        # Try nested schema_graph format
        if isinstance(data.get("schema_graph"), dict):
            raw_edges = data["schema_graph"].get("relations") or []

    for e in raw_edges:
        # Normalize keys
        src = str(e.get("source") or e.get("src") or e.get("from"))
        dst = str(e.get("target") or e.get("dst") or e.get("to"))
        etype = str(e.get("type") or e.get("edge") or e.get("label")).upper()
        
        if src and dst:
            G.add_edge(src, dst, type=etype)

    return G


def get_upstream_dependencies(G: nx.DiGraph, symbol_id: str, max_depth: int = 5) -> list[str]:
    """
    Who calls/uses this symbol? (Reverse dependency)
    Equivalent to: `mcwho` or `get_incoming_neighbors`
    
    Uses standard BFS predecessor traversal.
    """
    if symbol_id not in G:
        return []
    
    # In a directed graph A->B (A calls B), upstream of B is A.
    # networkx predecessor traversal handles this.
    # For lineage, we might want strictly "CALLS" edges.
    
    # Filter edges if needed (e.g. only 'CALLS' or 'IMPORTS')
    # For now, we take all incoming edges up to depth.
    
    # nx.ancestors returns ALL ancestors. For limited depth, we do BFS.
    visited = set()
    queue = [(symbol_id, 0)]
    upstream = []
    
    while queue:
        current, depth = queue.pop(0)
        if depth >= max_depth:
            continue
            
        for pred in G.predecessors(current):
            if pred not in visited:
                visited.add(pred)
                upstream.append(pred)
                queue.append((pred, depth + 1))
                
    return upstream


def get_downstream_dependencies(G: nx.DiGraph, symbol_id: str, max_depth: int = 5) -> list[str]:
    """
    What does this symbol call/use?
    Equivalent to: `get_outgoing_neighbors`
    """
    if symbol_id not in G:
        return []
        
    # Standard BFS successors
    visited = set()
    queue = [(symbol_id, 0)]
    downstream = []
    
    while queue:
        current, depth = queue.pop(0)
        if depth >= max_depth:
            continue
            
        for succ in G.successors(current):
            if succ not in visited:
                visited.add(succ)
                downstream.append(succ)
                queue.append((succ, depth + 1))
                
    return downstream


def get_centrality_scores(G: nx.DiGraph, top_k: int = 10) -> list[tuple[str, float]]:
    """
    Calculate PageRank or Degree Centrality to find "hotspot" code.
    This is nearly impossible with basic SQL.
    """
    # PageRank interprets A->B as "A votes for B".
    # In code, "A calls B" means B is important (used by many).
    try:
        scores = nx.pagerank(G)
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_k]
    except Exception as e:
        logger.warning(f"Centrality calc failed: {e}")
        return []

def get_shortest_path(G: nx.DiGraph, source: str, target: str) -> list[str] | None:
    """
    Find the shortest dependency chain between two symbols.
    """
    try:
        return nx.shortest_path(G, source, target)
    except nx.NetworkXNoPath:
        return None
    except nx.NodeNotFound:
        return None
