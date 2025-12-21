
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from llmc.rag.schema import Entity


@dataclass
class SymbolMatch:
    """Represents a potential match for a symbol query."""

    entity: Entity
    score: float
    match_type: str  # e.g., "exact", "case-insensitive", "suffix", "contains"

    def __repr__(self) -> str:
        return f"SymbolMatch(score={self.score:.2f}, type='{self.match_type}', entity='{self.entity.id}')"


# --- Scoring Constants ---
EXACT_MATCH_SCORE = 1.0
CASE_INSENSITIVE_MATCH_SCORE = 0.9
SUFFIX_MATCH_SCORE = 0.7
CONTAINS_MATCH_SCORE = 0.5


def _get_entity_priority(entity: Entity) -> int:
    """Assign a priority to an entity kind for stable sorting."""
    kind_priority = {
        "class": 10,
        "interface": 9,
        "function": 8,
        "method": 7,
        "type": 6,
        "variable": 5,
    }
    return kind_priority.get(entity.kind, 0)


def resolve_symbol(
    symbol: str, graph, max_results: int = 5
) -> list[SymbolMatch]:
    """
    Finds the best matches for a symbol in the graph using a scored,
    case-insensitive, and fuzzy matching algorithm.
    """
    if not symbol or not graph:
        return []

    query_lower = symbol.lower()
    matches: list[SymbolMatch] = []

    for entity in graph.entities:
        ent_name = entity.id.split(":", 1)[-1]
        ent_name_lower = ent_name.lower()

        if ent_name == symbol:
            matches.append(SymbolMatch(entity, EXACT_MATCH_SCORE, "exact"))
        elif ent_name_lower == query_lower:
            matches.append(
                SymbolMatch(entity, CASE_INSENSITIVE_MATCH_SCORE, "case-insensitive")
            )
        elif ent_name_lower.endswith(f".{query_lower}") or ent_name_lower.endswith(
            query_lower
        ):
            matches.append(SymbolMatch(entity, SUFFIX_MATCH_SCORE, "suffix"))
        elif query_lower in ent_name_lower:
            matches.append(SymbolMatch(entity, CONTAINS_MATCH_SCORE, "contains"))

    # Sort by score (desc), then by entity kind priority (desc), then alphabetically
    matches.sort(
        key=lambda m: (-m.score, -_get_entity_priority(m.entity), m.entity.id)
    )

    return matches[:max_results]


def resolve_symbol_best(symbol: str, graph) -> Optional[Entity]:
    """
    Returns the single best matching entity for a symbol, or None if no
    match is found.
    """
    matches = resolve_symbol(symbol, graph, max_results=1)
    return matches[0].entity if matches else None


# =============================================================================
# Dict-based resolution (for rag_nav compatibility)
# =============================================================================


@dataclass
class NodeMatch:
    """Represents a match for a raw node dict (lightweight version of SymbolMatch)."""

    node: dict
    score: float
    match_type: str  # e.g., "exact", "case-insensitive", "suffix", "contains"

    def __repr__(self) -> str:
        name = self.node.get("name") or self.node.get("id", "?")
        return f"NodeMatch(score={self.score:.2f}, type='{self.match_type}', node='{name}')"


def _extract_node_name(node: dict, name_key: str = "name") -> str:
    """Extract a clean name from a node dict."""
    raw_name = node.get(name_key) or node.get("id") or node.get("name", "")
    # Handle prefixed IDs like "class:Router" -> "Router"
    if ":" in raw_name:
        raw_name = raw_name.split(":", 1)[-1]
    return raw_name


def _get_node_kind_priority(node: dict) -> int:
    """Assign priority based on node kind for stable sorting."""
    kind = (node.get("kind") or node.get("type") or "").lower()
    kind_priority = {
        "class": 10,
        "interface": 9,
        "function": 8,
        "method": 7,
        "type": 6,
        "variable": 5,
    }
    return kind_priority.get(kind, 0)


def resolve_symbol_in_nodes(
    symbol: str,
    nodes: list[dict],
    max_results: int = 5,
    name_key: str = "name",
) -> list[NodeMatch]:
    """
    Resolve a symbol against raw node dicts (for rag_nav compatibility).

    Uses the same scoring algorithm as resolve_symbol():
    1. Exact match (score: 1.0)
    2. Case-insensitive exact (score: 0.9)
    3. Suffix match (score: 0.7)
    4. Contains match (score: 0.5)

    Args:
        symbol: The symbol to search for
        nodes: List of node dicts with 'name' or 'id' keys
        max_results: Maximum number of results to return
        name_key: Primary key to extract node name from

    Returns:
        List of NodeMatch objects, sorted by score (descending)
    """
    if not symbol or not nodes:
        return []

    query_lower = symbol.lower()
    matches: list[NodeMatch] = []

    for node in nodes:
        node_name = _extract_node_name(node, name_key)
        name_lower = node_name.lower()

        if node_name == symbol:
            matches.append(NodeMatch(node, EXACT_MATCH_SCORE, "exact"))
        elif name_lower == query_lower:
            matches.append(NodeMatch(node, CASE_INSENSITIVE_MATCH_SCORE, "case-insensitive"))
        elif name_lower.endswith(f".{query_lower}") or name_lower.endswith(query_lower):
            matches.append(NodeMatch(node, SUFFIX_MATCH_SCORE, "suffix"))
        elif query_lower in name_lower:
            matches.append(NodeMatch(node, CONTAINS_MATCH_SCORE, "contains"))

    # Sort by score (desc), kind priority (desc), then name alphabetically
    matches.sort(
        key=lambda m: (
            -m.score,
            -_get_node_kind_priority(m.node),
            _extract_node_name(m.node, name_key),
        )
    )

    return matches[:max_results]


def resolve_symbol_in_nodes_best(
    symbol: str,
    nodes: list[dict],
    name_key: str = "name",
) -> dict | None:
    """
    Returns the single best matching node dict, or None if no match is found.
    """
    matches = resolve_symbol_in_nodes(symbol, nodes, max_results=1, name_key=name_key)
    return matches[0].node if matches else None
