"""
Graph context builder for docgen - extracts entity and relation data from RAG.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def build_graph_context(
    repo_root: Path,
    relative_path: Path,
    db: Any,  # Database type from tools.rag.database
) -> str:
    """Build deterministic graph context for a file.
    
    Extracts entities, relations, and enrichment data from the RAG database
    and formats them as deterministic text for docgen backends.
    
    Args:
        repo_root: Absolute path to repository root
        relative_path: Path relative to repo root
        db: RAG database instance
        
    Returns:
        Formatted graph context string
    """
    from tools.rag.database import Database
    
    if not isinstance(db, Database):
        raise TypeError(f"Expected Database instance, got {type(db)}")
    
    # Check if graph indices exist
    graph_index_path = repo_root / ".llmc" / "rag_graph.json"
    if not graph_index_path.exists():
        logger.debug(f"No graph index found at {graph_index_path}")
        return _format_no_graph_context(relative_path)
    
    # Load graph indices
    try:
        with open(graph_index_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load graph index: {e}")
        return _format_no_graph_context(relative_path)
    
    # Find entities for this file
    file_str = str(relative_path)
    entities_for_file = []
    
    entities = graph_data.get("entities", {})
    for entity_id, entity_data in entities.items():
        # Check if entity belongs to this file
        # Graph entities have 'file_path' field
        if entity_data.get("file_path") == file_str:
            entities_for_file.append((entity_id, entity_data))
    
    if not entities_for_file:
        logger.debug(f"No entities found for {relative_path}")
        return _format_no_graph_context(relative_path)
    
    # Sort entities deterministically by ID
    entities_for_file.sort(key=lambda x: x[0])
    
    # Find relations involving these entities
    entity_ids = {eid for eid, _ in entities_for_file}
    relations_for_file = []
    
    relations = graph_data.get("relations", [])
    for relation in relations:
        src = relation.get("src")
        dst = relation.get("dst")
        
        # Include relation if either endpoint is in our file
        if src in entity_ids or dst in entity_ids:
            relations_for_file.append(relation)
    
    # Sort relations deterministically
    relations_for_file.sort(key=lambda r: (r.get("src", ""), r.get("edge", ""), r.get("dst", "")))
    
    # Fetch enrichment data for entities
    enrichments = {}
    for entity_id, entity_data in entities_for_file:
        span_hash = entity_data.get("span_hash")
        if span_hash:
            enrichment = db.fetch_enrichment_by_span_hash(span_hash)
            if enrichment:
                enrichments[entity_id] = enrichment
    
    # Format context
    return _format_graph_context(
        relative_path,
        entities_for_file,
        relations_for_file,
        enrichments,
    )


def _format_no_graph_context(relative_path: Path) -> str:
    """Format context when no graph data is available."""
    return f"""=== GRAPH_CONTEXT_BEGIN ===
file: {relative_path}
status: no_graph_data
message: No entity graph data available for this file
=== GRAPH_CONTEXT_END ==="""


def _format_graph_context(
    relative_path: Path,
    entities: list[tuple[str, dict]],
    relations: list[dict],
    enrichments: dict[str, Any],
) -> str:
    """Format graph context in deterministic text format.
    
    Args:
        relative_path: Path to file
        entities: List of (entity_id, entity_data) tuples
        relations: List of relation dicts
        enrichments: Dict mapping entity_id to enrichment data
        
    Returns:
        Formatted graph context string
    """
    lines = []
    lines.append("=== GRAPH_CONTEXT_BEGIN ===")
    lines.append(f"file: {relative_path}")
    lines.append(f"entity_count: {len(entities)}")
    lines.append(f"relation_count: {len(relations)}")
    lines.append("")
    
    # Format entities
    if entities:
        lines.append("entities:")
        for entity_id, entity_data in entities:
            lines.append(f"  - id: {entity_id}")
            
            # Add entity fields
            kind = entity_data.get("kind", "unknown")
            lines.append(f"    kind: {kind}")
            
            name = entity_data.get("name", "")
            if name:
                lines.append(f"    name: {name}")
            
            # Add span info if available
            start = entity_data.get("start_line")
            end = entity_data.get("end_line")
            if start is not None and end is not None:
                lines.append(f"    span: {start}-{end}")
            
            # Add enrichment summary if available
            if entity_id in enrichments:
                enrichment = enrichments[entity_id]
                summary = enrichment.summary
                if summary:
                    # Truncate long summaries
                    summary_oneline = summary.replace("\n", " ").strip()
                    if len(summary_oneline) > 120:
                        summary_oneline = summary_oneline[:117] + "..."
                    lines.append(f"    summary: {summary_oneline}")
    
    # Format relations
    if relations:
        lines.append("")
        lines.append("relations:")
        for relation in relations:
            src = relation.get("src", "")
            edge = relation.get("edge", "")
            dst = relation.get("dst", "")
            lines.append(f"  - src: {src}")
            lines.append(f"    edge: {edge}")
            lines.append(f"    dst: {dst}")
    
    lines.append("=== GRAPH_CONTEXT_END ===")
    
    return "\n".join(lines)


def load_graph_indices(repo_root: Path) -> dict | None:
    """Load graph indices from .llmc/rag_graph.json.
    
    Args:
        repo_root: Absolute path to repository root
        
    Returns:
        Graph data dict if available, None otherwise
    """
    graph_index_path = repo_root / ".llmc" / "rag_graph.json"
    
    if not graph_index_path.exists():
        return None
    
    try:
        with open(graph_index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load graph index from {graph_index_path}: {e}")
        return None
