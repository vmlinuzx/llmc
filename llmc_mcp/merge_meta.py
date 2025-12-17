#!/usr/bin/env python3
"""
Graph Merge Engine for MAASL.

Provides deterministic merging of concurrent knowledge graph updates with:
- Last-Write-Wins (LWW) semantics for properties
- Deterministic node/edge merging
- Conflict logging
- MAASL MERGE_META lock integration
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import time
from typing import Any

from llmc_mcp.maasl import ResourceDescriptor, get_maasl

logger = logging.getLogger("llmc-mcp.maasl.merge")


@dataclass
class GraphPatch:
    """
    Describes a set of graph modifications to apply.
    
    Used to batch multiple graph updates into a single atomic operation.
    """
    nodes_to_add: list[dict[str, Any]] = field(default_factory=list)
    edges_to_add: list[dict[str, Any]] = field(default_factory=list)
    properties_to_set: dict[str, dict[str, Any]] = field(default_factory=dict)  # {node_id: {key: value}}
    properties_to_clear: dict[str, list[str]] = field(default_factory=dict)  # {node_id: [keys]}
    
    def __post_init__(self):
        """Validate patch structure."""
        # Nodes should have at least 'id' and 'kind'
        for node in self.nodes_to_add:
            if 'id' not in node:
                raise ValueError(f"Node missing 'id': {node}")
            if 'kind' not in node:
                raise ValueError(f"Node missing 'kind': {node}")
        
        # Edges should have 'source', 'target', 'type'
        for edge in self.edges_to_add:
            if 'source' not in edge:
                raise ValueError(f"Edge missing 'source': {edge}")
            if 'target' not in edge:
                raise ValueError(f"Edge missing 'target': {edge}")
            if 'type' not in edge:
                raise ValueError(f"Edge missing 'type': {edge}")


@dataclass
class MergeResult:
    """Result of a merge operation."""
    success: bool
    nodes_added: int = 0
    edges_added: int = 0
    properties_updated: int = 0
    properties_cleared: int = 0
    conflicts: list[str] = field(default_factory=list)
    error: str | None = None
    merge_timestamp: float = field(default_factory=time.time)


class MergeEngine:
    """
    Deterministic graph merge engine with LWW semantics.
    
    Handles concurrent updates to knowledge graph with:
    - Atomic patch application
    - Last-Write-Wins for conflicting properties
    - Deterministic ordering for reproducibility
    - Conflict detection and logging
    """
    
    def __init__(self, graph_id: str = "main"):
        """
        Initialize merge engine.
        
        Args:
            graph_id: Logical graph identifier for MAASL locks
        """
        self.graph_id = graph_id
    
    def apply_patch(
        self,
        patch: GraphPatch,
        graph_store,  # GraphStore instance from llmc.rag.graph
        agent_id: str = "unknown",
        session_id: str = "unknown",
        operation_mode: str = "interactive",
    ) -> MergeResult:
        """
        Apply graph patch with MAASL protection.
        
        Uses Last-Write-Wins (LWW) semantics: later writes override earlier ones.
        All operations within a patch are atomic.
        
        Args:
            patch: GraphPatch describing changes
            graph_store: GraphStore instance to modify
            agent_id: ID of calling agent
            session_id: ID of calling session
            operation_mode: "interactive" or "batch"
        
        Returns:
            MergeResult with stats and conflicts
        """
        # Create resource descriptor for MAASL lock
        resource = ResourceDescriptor(
            resource_class="MERGE_META",
            identifier=self.graph_id,
        )
        
        # Define merge operation
        def protected_merge():
            return self._execute_merge(patch, graph_store)
        
        # Execute with MAASL protection
        maasl = get_maasl()
        try:
            result = maasl.call_with_stomp_guard(
                op=protected_merge,
                resources=[resource],
                intent="graph_merge",
                mode=operation_mode,
                agent_id=agent_id,
                session_id=session_id,
            )
            return result
        except Exception as e:
            logger.error(f"Graph merge failed for {agent_id}: {e}")
            return MergeResult(
                success=False,
                error=str(e),
            )
    
    def _execute_merge(
        self,
        patch: GraphPatch,
        graph_store,
    ) -> MergeResult:
        """
        Execute the actual merge logic.
        
        This runs within MAASL-protected section.
        """
        nodes_added = 0
        edges_added = 0
        properties_updated = 0
        properties_cleared = 0
        conflicts: list[str] = []
        
        try:
            # Step 1: Add nodes (deterministic order by ID)
            sorted_nodes = sorted(patch.nodes_to_add, key=lambda n: n['id'])
            for node in sorted_nodes:
                node_id = node['id']
                
                # Check if node exists
                existing = graph_store.entities.get(node_id)
                if existing:
                    # Node exists - log conflict but don't error (LWW)
                    conflicts.append(f"Node {node_id} already exists - using LWW")
                    # Update properties with LWW (into metadata)
                    for key, value in node.items():
                        if key not in ['id', 'kind', 'path']:  # Don't override structural fields
                            if not hasattr(existing, 'metadata'):
                                existing.metadata = {}
                            existing.metadata[key] = value
                else:
                    # New node - add it
                    from llmc.rag.schema import Entity
                    
                    # Extract core Entity fields
                    entity = Entity(
                        id=node['id'],
                        kind=node['kind'],
                        path=node.get('path', ''),
                        metadata={},
                    )
                    
                    # Put extra properties in metadata
                    for key, value in node.items():
                        if key not in ['id', 'kind', 'path']:
                            entity.metadata[key] = value
                    
                    graph_store.entities[node_id] = entity
                    nodes_added += 1
            
            # Step 2: Add edges (deterministic order by source, target, type)
            sorted_edges = sorted(
                patch.edges_to_add,
                key=lambda e: (e['source'], e['target'], e['type'])
            )
            for edge in sorted_edges:
                source = edge['source']
                target = edge['target']
                edge_type = edge['type']
                
                # Ensure both nodes exist
                if source not in graph_store.entities:
                    conflicts.append(f"Edge source {source} not found - skipping edge")
                    continue
                if target not in graph_store.entities:
                    conflicts.append(f"Edge target {target} not found - skipping edge")
                    continue
                
                # Add to adjacency list (avoid duplicates)
                if source not in graph_store.adjacency:
                    graph_store.adjacency[source] = {"outgoing": {}, "incoming": {}}
                
                if edge_type not in graph_store.adjacency[source]["outgoing"]:
                    graph_store.adjacency[source]["outgoing"][edge_type] = []
                
                if target not in graph_store.adjacency[source]["outgoing"][edge_type]:
                    graph_store.adjacency[source]["outgoing"][edge_type].append(target)
                    edges_added += 1
                    
                    # Update incoming edges on target
                    if target not in graph_store.adjacency:
                        graph_store.adjacency[target] = {"outgoing": {}, "incoming": {}}
                    
                    reverse_type = graph_store._reverse_edge_name(edge_type)
                    if reverse_type not in graph_store.adjacency[target]["incoming"]:
                        graph_store.adjacency[target]["incoming"][reverse_type] = []
                    
                    if source not in graph_store.adjacency[target]["incoming"][reverse_type]:
                        graph_store.adjacency[target]["incoming"][reverse_type].append(source)
                else:
                    conflicts.append(
                        f"Edge {source} -{edge_type}-> {target} already exists"
                    )
            
            # Step 3: Set properties (LWW)
            for node_id, props in patch.properties_to_set.items():
                if node_id not in graph_store.entities:
                    conflicts.append(f"Node {node_id} not found for property update")
                    continue
                
                entity = graph_store.entities[node_id]
                if not hasattr(entity, 'metadata'):
                    entity.metadata = {}
                    
                for key, value in props.items():
                    entity.metadata[key] = value
                    properties_updated += 1
            
            # Step 4: Clear properties
            for node_id, keys in patch.properties_to_clear.items():
                if node_id not in graph_store.entities:
                    conflicts.append(f"Node {node_id} not found for property clear")
                    continue
                
                entity = graph_store.entities[node_id]
                if hasattr(entity, 'metadata'):
                    for key in keys:
                        if key in entity.metadata:
                            del entity.metadata[key]
                            properties_cleared += 1
            
            # Log conflicts if any
            if conflicts:
                logger.warning(f"Graph merge had {len(conflicts)} conflicts (using LWW)")
                for conflict in conflicts[:5]:  # Log first 5
                    logger.warning(f"  - {conflict}")
            
            return MergeResult(
                success=True,
                nodes_added=nodes_added,
                edges_added=edges_added,
                properties_updated=properties_updated,
                properties_cleared=properties_cleared,
                conflicts=conflicts,
            )
            
        except Exception as e:
            logger.error(f"Merge execution failed: {e}")
            return MergeResult(
                success=False,
                error=str(e),
                conflicts=conflicts,
            )


def get_merge_engine(graph_id: str = "main") -> MergeEngine:
    """
    Factory function for MergeEngine.
    
    Args:
        graph_id: Logical graph identifier
    
    Returns:
        MergeEngine instance
    """
    return MergeEngine(graph_id=graph_id)
