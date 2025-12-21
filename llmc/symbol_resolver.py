
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
