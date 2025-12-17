"""
Query-Time Enrichment Module for LLMC RAG

Integrates schema graph with vector search to provide hybrid retrieval
with relationship awareness.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from pathlib import Path
import re

# Hoisted imports
from typing import Any

from ..database import Database

# GraphNeighbor and GraphStore live in graph_store.py
# (Renamed from graph.py to avoid shadowing by the graph/ package)
from ..graph_store import GraphNeighbor, GraphStore

from ..types import SpanRecord
from ..workers import enrichment_plan, execute_enrichment


@dataclass
class EnrichmentFeatures:
    """Features extracted from query for router decision-making"""

    relation_task: bool = False  # Query asks for relationships
    relation_density: float = 0.0  # Fraction of context from graph (0-1)
    graph_coverage: float = 0.0  # How many detected entities found in graph
    complexity_score: int = 0  # Query complexity estimate (0-10)
    detected_entities: list[str] = None  # Entities found in query
    fallback_reason: str | None = None  # Why enrichment failed, if applicable

    def __post_init__(self):
        if self.detected_entities is None:
            self.detected_entities = []


class QueryAnalyzer:
    """Analyzes queries to detect entities and relationships"""

    # Relation keywords that indicate relationship queries
    RELATION_KEYWORDS = {
        "calls",
        "call",
        "calling",
        "invokes",
        "uses",
        "use",
        "using",
        "depends",
        "dependency",
        "reads",
        "read",
        "writes",
        "write",
        "inherits",
        "inherit",
        "extends",
        "extend",
        "returns",
        "return",
        "breaks",
        "break",
        "impacts",
        "impact",
        "which",
        "what",
        "where",
        "trace",
    }

    def __init__(self, graph_store: GraphStore):
        self.graph_store = graph_store

    def analyze(self, query: str) -> EnrichmentFeatures:
        """
        Analyze query to extract enrichment features.

        Args:
            query: User's query string

        Returns:
            EnrichmentFeatures object
        """
        features = EnrichmentFeatures()

        # Detect relationship keywords
        query_lower = query.lower()
        features.relation_task = any(keyword in query_lower for keyword in self.RELATION_KEYWORDS)

        # Detect entities (camelCase, snake_case, or quoted identifiers)
        features.detected_entities = self._detect_entities(query)

        # Calculate graph coverage (what % of detected entities exist in graph)
        if features.detected_entities:
            found_count = sum(
                1
                for entity_id in features.detected_entities
                if self.graph_store.get_entity(entity_id) is not None
            )
            features.graph_coverage = found_count / len(features.detected_entities)

        # Estimate complexity
        features.complexity_score = self._estimate_complexity(query, features)

        return features

    def _detect_entities(self, query: str) -> list[str]:
        """
        Extract potential entity identifiers from query.

        Looks for:
        - camelCase identifiers
        - snake_case identifiers
        - Quoted identifiers like 'getUserData'
        """
        entities = []

        # Pattern for camelCase and snake_case
        identifier_pattern = r"\b[a-z][a-zA-Z0-9_]*[a-zA-Z0-9]\b"
        matches = re.findall(identifier_pattern, query)

        for match in matches:
            # Check if it exists in graph (fuzzy match)
            fuzzy_matches = self.graph_store.find_entities_by_pattern(match)
            if fuzzy_matches:
                entities.extend([e.id for e in fuzzy_matches[:3]])  # Top 3 matches

        # Pattern for quoted identifiers
        quoted_pattern = r'[\'"`]([a-zA-Z_][a-zA-Z0-9_\.]*)[\'"`]'
        quoted_matches = re.findall(quoted_pattern, query)

        for match in quoted_matches:
            fuzzy_matches = self.graph_store.find_entities_by_pattern(match)
            if fuzzy_matches:
                entities.extend([e.id for e in fuzzy_matches[:3]])

        return list(set(entities))  # Deduplicate

    def _estimate_complexity(self, query: str, features: EnrichmentFeatures) -> int:
        """
        Estimate query complexity on scale 0-10.

        Factors:
        - Number of entities mentioned
        - Number of relation keywords
        - Query length
        - Multi-hop indicators ("chain", "transitive", "indirect")
        """
        score = 0

        # Entity count contribution (0-4 points)
        score += min(len(features.detected_entities), 4)

        # Relation keyword count (0-3 points)
        relation_count = sum(1 for keyword in self.RELATION_KEYWORDS if keyword in query.lower())
        score += min(relation_count, 3)

        # Multi-hop indicators (0-2 points)
        multihop_keywords = ["chain", "transitive", "indirect", "all", "complete"]
        if any(keyword in query.lower() for keyword in multihop_keywords):
            score += 2

        # Query length contribution (0-1 point)
        if len(query.split()) > 15:
            score += 1

        return min(score, 10)


class HybridRetriever:
    """
    Combines vector search with graph traversal for hybrid retrieval.
    """

    def __init__(self, graph_store: GraphStore, analyzer: QueryAnalyzer):
        self.graph_store = graph_store
        self.analyzer = analyzer

    def retrieve(
        self,
        query: str,
        vector_results: list[SpanRecord],
        max_graph_results: int = 15,
        max_hops: int = 1,
    ) -> tuple[list[SpanRecord], EnrichmentFeatures]:
        """
        Hybrid retrieval: merge vector results with graph-based results.

        Args:
            query: User query
            vector_results: Results from vector search (existing RAG)
            max_graph_results: Max results to add from graph traversal
            max_hops: Maximum hops for graph traversal (1 or 2)

        Returns:
            Tuple of (merged_results, enrichment_features)
        """
        # Analyze query
        features = self.analyzer.analyze(query)

        # If no relation task or no entities detected, return vector results only
        if not features.relation_task or not features.detected_entities:
            features.relation_density = 0.0
            features.fallback_reason = "No relationship task or entities detected"
            return vector_results, features

        # Graph traversal for detected entities
        graph_neighbors = []
        for entity_id in features.detected_entities:
            neighbors = self.graph_store.get_neighbors(
                entity_id, max_hops=max_hops, max_neighbors=max_graph_results
            )
            graph_neighbors.extend(neighbors)

        # If no graph neighbors found, return vector results only
        if not graph_neighbors:
            features.relation_density = 0.0
            features.fallback_reason = "No graph neighbors found for entities"
            return vector_results, features

        # Convert graph neighbors to SpanRecords
        # (In real implementation, this would fetch actual code spans)
        # For now, we'll create placeholder records with the file paths
        graph_results = self._neighbors_to_spans(graph_neighbors)

        # Merge results (simple append for v1, reranking in v2)
        merged = self._merge_results(vector_results, graph_results)

        # Calculate relation density
        features.relation_density = len(graph_results) / len(merged) if merged else 0.0

        return merged, features

    def _neighbors_to_spans(self, neighbors: list[GraphNeighbor]) -> list[SpanRecord]:
        """Convert graph neighbors to SpanRecords"""
        # Placeholder implementation
        # In production, this would fetch actual code spans from the paths
        spans = []

        for neighbor in neighbors:
            # Parse path format: "file.py:start-end"
            parts = neighbor.path.split(":")
            if len(parts) == 2:
                file_path_str = parts[0]
                line_range = parts[1]

                # Parse line range
                try:
                    start_line, end_line = map(int, line_range.split("-"))
                except ValueError:
                    continue

                # Create a span record (would normally fetch from disk/database)
                # For now, just create a marker span
                span = SpanRecord(
                    file_path=Path(file_path_str),
                    lang="python",  # Would detect from extension
                    symbol=neighbor.entity_id,
                    kind="function",  # Would get from entity metadata
                    start_line=start_line,
                    end_line=end_line,
                    byte_start=0,  # Would calculate from file
                    byte_end=0,
                    span_hash=f"graph_{neighbor.entity_id}",
                )
                spans.append(span)

        return spans

    def _merge_results(
        self, vector_results: list[SpanRecord], graph_results: list[SpanRecord]
    ) -> list[SpanRecord]:
        """
        Merge and deduplicate vector + graph results.

        Simple append in v1. In v2, this would use reranking.
        """
        # Deduplicate by span_hash
        seen_hashes = set()
        merged = []

        for result in vector_results + graph_results:
            if result.span_hash not in seen_hashes:
                merged.append(result)
                seen_hashes.add(result.span_hash)

        return merged


# ---------------------------------------------------------------------------
# Phase 1 – Enrichment orchestration helpers
#
# These helpers provide a small, testable façade over the lower-level


@dataclass
class EnrichmentBatchResult:
    """Summary of a batch enrichment run.

    This is deliberately minimal – it can be extended in later phases once the
    CLI and integration tests are wired up.
    """

    total_planned: int
    attempted: int
    succeeded: int
    failed: int
    errors: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_planned": self.total_planned,
            "attempted": self.attempted,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "errors": list(self.errors),
        }


def enrich_spans(
    db: Database,
    repo_root: Path,
    llm_call: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    limit: int = 32,
    model: str = "local-llm",
    cooldown_seconds: int = 0,
    logger: logging.Logger | None = None,
) -> EnrichmentBatchResult:
    """Enrich pending spans in the database.

    This is a thin, structured wrapper around :func:`execute_enrichment` that:

    - leaves the existing LLM call contract untouched (``llm_call`` takes the
      legacy prompt-dict used by the worker),
    - returns a structured :class:`EnrichmentBatchResult` instead of a bare
      ``(successes, errors)`` tuple.

    Future phases can add chain / tier / backend-cascade selection here
    without changing callers.
    """
    # Discover the current plan size for observability. We intentionally
    # keep planning and execution loosely coupled in Phase 1 – tighter
    # integration is handled in a later phase.
    try:
        planned = enrichment_plan(db, repo_root, limit=limit, cooldown_seconds=cooldown_seconds)
        total_planned = len(planned)
    except Exception:
        # Planning is best-effort here; we never want it to block execution.
        total_planned = 0

    successes, errors = execute_enrichment(
        db=db,
        repo_root=repo_root,
        llm_call=llm_call,
        limit=limit,
        model=model,
        cooldown_seconds=cooldown_seconds,
    )
    attempted = successes + len(errors)

    if logger:
        logger.info(
            "enrich_spans: planned=%d attempted=%d succeeded=%d failed=%d",
            total_planned,
            attempted,
            successes,
            len(errors),
        )

    return EnrichmentBatchResult(
        total_planned=total_planned,
        attempted=attempted,
        succeeded=successes,
        failed=len(errors),
        errors=errors,
    )


def batch_enrich(
    db: Database,
    repo_root: Path,
    llm_call: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    batch_size: int = 32,
    model: str = "local-llm",
    cooldown_seconds: int = 0,
    logger: logging.Logger | None = None,
) -> EnrichmentBatchResult:
    """High-level batch enrichment entry point.

    This function is a small, DB-backed batch runner that delegates to
    :func:`enrich_spans`, which in turn relies on the existing
    `pending_enrichments` / `execute_enrichment` pipeline. In other
    words: it processes the next N spans that currently have no
    enrichment rows, using the provided ``llm_call``.


    ``batch_enrich`` is intentionally a very small wrapper around
    :func:`enrich_spans`. In later phases this is where we will introduce
    configuration-driven chains, tiers, and retry policies.

    For Phase 1 it simply forwards to :func:`enrich_spans` using ``batch_size``
    as the ``limit``.
    """
    return enrich_spans(
        db=db,
        repo_root=repo_root,
        llm_call=llm_call,
        limit=batch_size,
        model=model,
        cooldown_seconds=cooldown_seconds,
        logger=logger,
    )
