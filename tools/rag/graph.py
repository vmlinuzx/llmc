"""
Graph Storage and Traversal Module for LLMC RAG

Provides in-memory adjacency list for O(1) neighbor lookups,
1-2 hop traversal with cycle detection, and integration with vector search.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .schema import Entity, Relation, SchemaGraph


@dataclass
class GraphNeighbor:
    """Represents a neighbor in the graph with metadata"""
    entity_id: str
    edge_type: str
    distance: int  # Hop count from query entity
    path: str  # File path for retrieving source code


class GraphStore:
    """
    In-memory graph storage with adjacency lists for fast traversal.
    
    Structure:
        adjacency[entity_id] = {
            "outgoing": {"calls": [neighbor_ids], "uses": [...]},
            "incoming": {"called_by": [neighbor_ids], ...}
        }
    """
    
    def __init__(self):
        self.adjacency: Dict[str, Dict[str, Dict[str, List[str]]]] = defaultdict(
            lambda: {"outgoing": defaultdict(list), "incoming": defaultdict(list)}
        )
        self.entities: Dict[str, Entity] = {}  # entity_id -> Entity
        self.indexed_at: str = ""
        self.repo: str = ""
    
    def load_from_schema(self, graph: SchemaGraph):
        """Load graph from SchemaGraph object"""
        self.indexed_at = graph.indexed_at
        self.repo = graph.repo
        
        # Index entities
        for entity in graph.entities:
            self.entities[entity.id] = entity
        
        # Build adjacency lists
        for relation in graph.relations:
            # Outgoing edge
            self.adjacency[relation.src]["outgoing"][relation.edge].append(relation.dst)
            
            # Incoming edge (reverse direction)
            reverse_edge = self._reverse_edge_name(relation.edge)
            self.adjacency[relation.dst]["incoming"][reverse_edge].append(relation.src)
    
    def load_from_file(self, path: Path):
        """Load graph from JSON file.

        Supports both raw SchemaGraph JSON files and the nested
        `schema_graph` payload inside `.llmc/rag_graph.json`.
        """
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        # If this is a RAG Nav graph artifact, extract the nested schema_graph.
        payload = data.get("schema_graph") if isinstance(data, dict) else None
        if isinstance(payload, dict):
            graph = SchemaGraph.from_dict(payload)
        else:
            # Fallback to the flat SchemaGraph format.
            graph = SchemaGraph.from_dict(data)

        self.load_from_schema(graph)
    
    def save_to_file(self, path: Path):
        """Save graph structure (delegates to SchemaGraph for actual saving)"""
        # Reconstruct SchemaGraph from adjacency list
        graph = SchemaGraph(
            indexed_at=self.indexed_at,
            repo=self.repo,
            entities=list(self.entities.values()),
            relations=self._extract_relations()
        )
        graph.save(path)
    
    def _extract_relations(self) -> List[Relation]:
        """Reconstruct relations from adjacency list"""
        relations = []
        seen = set()
        
        for entity_id, neighbors in self.adjacency.items():
            for edge_type, target_ids in neighbors["outgoing"].items():
                for target_id in target_ids:
                    key = (entity_id, edge_type, target_id)
                    if key not in seen:
                        relations.append(Relation(src=entity_id, edge=edge_type, dst=target_id))
                        seen.add(key)
        
        return relations
    
    def get_neighbors(
        self,
        entity_id: str,
        max_hops: int = 1,
        edge_filter: Optional[Set[str]] = None,
        max_neighbors: int = 50
    ) -> List[GraphNeighbor]:
        """
        Traverse graph from entity_id up to max_hops.
        
        Args:
            entity_id: Starting entity
            max_hops: Maximum distance to traverse (1 or 2)
            edge_filter: If set, only follow these edge types
            max_neighbors: Maximum neighbors to return (prevent explosion)
        
        Returns:
            List of GraphNeighbor objects with entity IDs, edge types, distances
        """
        if entity_id not in self.adjacency:
            return []
        
        visited: Set[str] = {entity_id}
        neighbors: List[GraphNeighbor] = []
        queue: List[Tuple[str, int]] = [(entity_id, 0)]
        
        while queue and len(neighbors) < max_neighbors:
            current_id, distance = queue.pop(0)
            
            if distance >= max_hops:
                continue
            
            # Get both outgoing and incoming edges
            current_edges = self.adjacency[current_id]
            
            for direction in ["outgoing", "incoming"]:
                for edge_type, target_ids in current_edges[direction].items():
                    # Apply edge filter if specified
                    if edge_filter and edge_type not in edge_filter:
                        continue
                    
                    for target_id in target_ids:
                        if target_id in visited:
                            continue  # Cycle detection
                        
                        visited.add(target_id)
                        
                        # Add to results if target exists
                        if target_id in self.entities:
                            entity = self.entities[target_id]
                            neighbors.append(
                                GraphNeighbor(
                                    entity_id=target_id,
                                    edge_type=edge_type,
                                    distance=distance + 1,
                                    path=entity.path
                                )
                            )
                        
                        # Add to queue for next hop
                        if distance + 1 < max_hops:
                            queue.append((target_id, distance + 1))
        
        return neighbors[:max_neighbors]
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID"""
        return self.entities.get(entity_id)
    
    def find_entities_by_pattern(self, pattern: str, kind: Optional[str] = None) -> List[Entity]:
        """
        Find entities matching a pattern (substring search).
        
        Args:
            pattern: String to search for in entity IDs
            kind: Optional filter by entity kind
        
        Returns:
            List of matching entities
        """
        pattern_lower = pattern.lower()
        matches = []
        
        for entity_id, entity in self.entities.items():
            if kind and entity.kind != kind:
                continue
            
            if pattern_lower in entity_id.lower():
                matches.append(entity)
        
        return matches
    
    def get_statistics(self) -> Dict:
        """Get graph statistics for monitoring"""
        return {
            "total_entities": len(self.entities),
            "total_edges": sum(
                len(targets)
                for entity_data in self.adjacency.values()
                for edge_targets in entity_data["outgoing"].values()
                for targets in [edge_targets]
            ),
            "entity_kinds": self._count_entity_kinds(),
            "edge_types": self._count_edge_types(),
            "indexed_at": self.indexed_at,
        }
    
    def _count_entity_kinds(self) -> Dict[str, int]:
        """Count entities by kind"""
        counts = defaultdict(int)
        for entity in self.entities.values():
            counts[entity.kind] += 1
        return dict(counts)
    
    def _count_edge_types(self) -> Dict[str, int]:
        """Count edges by type"""
        counts = defaultdict(int)
        for entity_data in self.adjacency.values():
            for edge_type, targets in entity_data["outgoing"].items():
                counts[edge_type] += len(targets)
        return dict(counts)
    
    def _reverse_edge_name(self, edge: str) -> str:
        """Get the reverse edge name for incoming edges"""
        reverse_map = {
            "calls": "called_by",
            "uses": "used_by",
            "reads": "read_by",
            "writes": "written_by",
            "extends": "extended_by",
            "returns": "returned_by",
        }
        return reverse_map.get(edge, f"{edge}_reverse")
