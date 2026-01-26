from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import struct
from typing import Any

import numpy as np

from ..config import (
    embedding_model_dim,
    embedding_model_name,
    get_multi_route_config,
    index_path_for_read,
    is_query_routing_enabled,
    load_config,
    resolve_route,
)

# Conditional import for telemetry - allows the module to work without llmc dependency
try:
    from llmc.te.telemetry import log_routing_event
except ImportError:
    # No-op fallback when llmc module is not available
    def log_routing_event(  # type: ignore
        mode: str, details: dict[str, Any], repo_root: Path | None = None
    ) -> None:
        """No-op fallback for telemetry logging when llmc module is unavailable."""
        pass


# Conditional import for routing components - allows the module to work without llmc dependency
try:
    from llmc.routing.fusion import fuse_scores
except ImportError:
    # No-op fallback when llmc module is not available
    def fuse_scores(  # type: ignore
        route_results: dict[str, list[dict[str, Any]]], route_weights: dict[str, float]
    ) -> list[dict[str, Any]]:
        """No-op fallback for score fusion when llmc module is unavailable."""
        return []


try:
    from llmc.routing.router import create_router
except ImportError:
    # No-op fallback when llmc module is not available
    def create_router(config: dict[str, Any]) -> Any:  # type: ignore
        """No-op fallback for router creation when llmc module is unavailable."""
        return None


import logging

from llmc.core import find_repo_root
from llmc.rag.config import ConfigError  # Added import
from llmc.rag.scoring import Scorer

from ..database import Database
from ..embeddings import HASH_MODELS, build_embedding_backend

logger = logging.getLogger(__name__)



def _norm(vector: np.ndarray) -> float:
    return np.linalg.norm(vector)


def _dot(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b)


def _unpack_vector(blob: bytes) -> list[float]:
    dim = len(blob) // 4
    return list(struct.unpack(f"<{dim}f", blob))


def _safe_load(val: str | None) -> Any:
    """Safely parse JSON string, returning original value on failure."""
    if not val:
        return None
    try:
        return json.loads(val)
    except (ValueError, TypeError):
        return val




@dataclass(frozen=True)
class SpanSearchResult:
    span_hash: str
    path: Path
    symbol: str
    kind: str
    start_line: int
    end_line: int
    score: float
    summary: str | None
    normalized_score: float = 0.0
    debug_info: dict[str, Any] | None = field(default=None)


def _score_candidates(
    query_vector: np.ndarray,
    query_norm: float,
    rows: Iterable,
    query_text: str | None = None,
    repo_root: Path | None = None,
) -> list[SpanSearchResult]:
    results: list[SpanSearchResult] = []
    scorer = Scorer(repo_root)
    intent = scorer.detect_intent(query_text) if query_text else "neutral"

    for row in rows:
        vector = np.array(_unpack_vector(row["vec"]))
        vector_norm = _norm(vector)
        if query_norm == 0.0 or vector_norm == 0.0:
            continue
        similarity = _dot(query_vector, vector) / (query_norm * vector_norm)

        if query_text:
            similarity += scorer.score_filename_match(query_text, row["file_path"])

        # Apply extension-based boost (code files up, docs down)
        similarity += scorer.score_extension(row["file_path"], intent=intent)

        # Normalize to 0-100 range, clamping at boundaries
        # Raw similarity can be > 1.0 due to boosts
        norm_score = max(0.0, min(100.0, similarity * 100.0))

        results.append(
            SpanSearchResult(
                span_hash=row["span_hash"],
                path=Path(row["file_path"]),
                symbol=row["symbol"],
                kind=row["kind"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                score=float(similarity),
                summary=row["summary"] or None,
                normalized_score=float(norm_score),
            )
        )
    results.sort(key=lambda item: item.score, reverse=True)
    return results


def _enrich_debug_info(
    results: list[SpanSearchResult],
    repo_root: Path,
    db_path: Path,
) -> list[SpanSearchResult]:
    """Attach debug metadata (graph, enrichment, provenance) to results."""
    # 1. Load Enrichment Data
    enrich_map = {}
    if db_path.exists():
        db = Database(db_path)
        try:
            # Fetch enrichments for these span hashes
            hashes = [r.span_hash for r in results]
            if hashes:
                placeholders = ",".join("?" for _ in hashes)
                rows = db.conn.execute(  # nosec B608
                    f"""
                    SELECT span_hash, summary, inputs, outputs, side_effects, pitfalls, evidence, usage_snippet
                    FROM enrichments
                    WHERE span_hash IN ({placeholders})
                    """,
                    hashes,
                ).fetchall()
                for row in rows:
                    enrich_map[row["span_hash"]] = {
                        "summary": row["summary"],
                        "inputs": _safe_load(row["inputs"]),
                        "outputs": _safe_load(row["outputs"]),
                        "side_effects": _safe_load(row["side_effects"]),
                        "pitfalls": _safe_load(row["pitfalls"]),
                        "evidence_count": (
                            len(json.loads(row["evidence"])) if row["evidence"] else 0
                        ),
                    }
        except Exception:
            pass
        finally:
            db.close()

    # 2. Load Graph Data (Best Effort)
    graph_map = {}
    graph_path = repo_root / ".llmc" / "rag_graph.json"
    if graph_path.exists():
        try:
            # We do a lazy load or manual parse to avoid huge overhead if possible,
            # but SchemaGraph.load is standard.
            from ..schema import SchemaGraph

            graph = SchemaGraph.load(graph_path)

            # Index entities by span_hash or fuzzy location
            # For now, let's try to match by file path and line overlap
            # Optimization: Pre-index graph entities by file path
            entities_by_file: dict[str, list[Any]] = {}
            for ent in graph.entities:
                # entity.path is "path:lines" or just path
                # Schema 2.0 entities have file_path attribute
                fpath = getattr(ent, "file_path", None)
                if not fpath:
                    # Fallback to parsing "src/foo.py:10-20"
                    parts = ent.path.rsplit(":", 1)
                    if len(parts) == 2:
                        fpath = parts[0]

                if fpath:
                    # Normalize to string relative to repo root if possible
                    entities_by_file.setdefault(fpath, []).append(ent)

            # Map relations by src/dst
            rels_by_src: dict[str, list[Any]] = {}
            rels_by_dst: dict[str, list[Any]] = {}
            for rel in graph.relations:
                rels_by_src.setdefault(rel.src, []).append(rel)
                rels_by_dst.setdefault(rel.dst, []).append(rel)

            for res in results:
                # Try to find matching entity
                res_path_str = (
                    str(res.path.relative_to(repo_root))
                    if res.path.is_absolute()
                    else str(res.path)
                )
                candidates = entities_by_file.get(res_path_str, [])

                matched_ent = None
                # Simple overlap check
                for ent in candidates:
                    # Check lines if available
                    e_start = getattr(ent, "start_line", None)
                    e_end = getattr(ent, "end_line", None)

                    if e_start is None:
                        # Try parse from path string
                        try:
                            suffix = ent.path.rsplit(":", 1)[-1]
                            if "-" in suffix:
                                s, e = suffix.split("-")
                                e_start, e_end = int(s), int(e)
                            else:
                                e_start = int(suffix)
                                e_end = e_start
                        except Exception:
                            continue

                    if e_start is None:
                        continue
                    if e_end is None:
                        e_end = e_start

                    # Check overlap
                    if not (e_end < res.start_line or e_start > res.end_line):
                        matched_ent = ent
                        break

                if matched_ent:
                    # Gather neighbors
                    parents: list[str] = []
                    children: list[str] = []
                    related_code: list[str] = []
                    related_tests: list[str] = []
                    related_docs: list[str] = []

                    # Outgoing edges
                    for rel in rels_by_src.get(matched_ent.id, []):
                        target = rel.dst
                        if rel.edge == "calls":
                            related_code.append(f"Calls: {target}")
                        elif rel.edge == "extends":
                            parents.append(f"Extends: {target}")

                    # Incoming edges
                    for rel in rels_by_dst.get(matched_ent.id, []):
                        source = rel.src
                        if rel.edge == "calls":
                            related_code.append(f"Called by: {source}")
                        elif rel.edge == "extends":
                            children.append(f"Subclass: {source}")
                        elif "test" in source.lower() or "test" in rel.edge:
                            related_tests.append(source)

                    # Implicit parent by name (e.g. mod.Class.func -> mod.Class)
                    if "." in matched_ent.id:
                        parent_id = matched_ent.id.rsplit(".", 1)[0]
                        parents.append(parent_id)

                    graph_map[res.span_hash] = {
                        "node_type": matched_ent.kind,
                        "node_id": matched_ent.id,
                        "parents": parents[:3],
                        "children": children[:3],
                        "related_code": related_code[:5],
                        "related_tests": related_tests[:3],
                        "related_docs": related_docs[:3],
                    }

        except Exception:
            # Graph load failure is non-critical for debug view
            pass

    # 3. Assemble Debug Info
    enriched_results = []
    for res in results:
        debug = {
            "search": {
                "rank": -1,  # To be filled by caller or implicit order
                "score": res.score,
                "embedding_similarity": res.score,
                # No reranker in this simple search pipeline
            },
            "enrichment": enrich_map.get(res.span_hash, None),
            "graph": graph_map.get(res.span_hash, None),
            "provenance": {
                "kind": res.kind,
                # Last commit could be fetched via git if slow is ok, skipping for speed
            },
        }
        enriched_results.append(
            SpanSearchResult(
                span_hash=res.span_hash,
                path=res.path,
                symbol=res.symbol,
                kind=res.kind,
                start_line=res.start_line,
                end_line=res.end_line,
                score=res.score,
                summary=res.summary,
                normalized_score=res.normalized_score,
                debug_info=debug,
            )
        )

    return enriched_results


def search_spans(
    query: str,
    *,
    limit: int = 5,
    repo_root: Path | None = None,
    model_override: str | None = None,
    debug: bool = False,
    tool_context: dict[str, Any] | None = None,
) -> list[SpanSearchResult]:
    """Execute a simple cosine-similarity search over the local `.rag` index."""
    repo = repo_root or find_repo_root()
    db_path = index_path_for_read(repo)
    if not db_path.exists():
        raise FileNotFoundError(
            f"No embedding index found at {db_path}. Run `python -m llmc.rag.cli index` and `embed --execute` first."
        )

    # 1. Classify Query
    primary_route = "docs"
    route_decision = None

    if is_query_routing_enabled(repo):
        config = load_config(repo)
        router = create_router(config)
        classification = router.decide_route(query, tool_context=tool_context)
        primary_route = classification["route_name"]
        route_decision = classification

        logger.debug(
            "Query routing classification: route='%s' confidence=%.2f reasons=%s",
            primary_route,
            classification["confidence"],
            classification["reasons"],
        )
        log_routing_event(
            mode="routing_query_classify",
            details={
                "route_name": primary_route,
                "confidence": f"{classification['confidence']:.2f}",
                "reasons": ";".join(classification["reasons"]),
                "query_hash": hash(query),
            },
            repo_root=repo,
        )

    # 2. Determine Routes (Single or Multi)
    # This helper handles the enable_multi_route check internally
    routes_to_query = get_multi_route_config(primary_route, repo)

    if len(routes_to_query) > 1:
        logger.debug(f"Multi-route retrieval enabled. Fan-out: {routes_to_query}")

    # 3. Execute Searches
    results_by_route: dict[str, list[dict[str, Any]]] = {}
    route_weights: dict[str, float] = {}

    # Cache embeddings by profile name to avoid redundant API calls
    # Key: profile_name, Value: (query_vector, query_norm)
    embedding_cache: dict[str, tuple[np.ndarray, float]] = {}

    config = load_config(repo)
    db = Database(db_path)

    try:
        for route_name, weight in routes_to_query:
            route_weights[route_name] = weight

            try:
                profile_name, index_name = resolve_route(route_name, "query", repo)
            except ConfigError as e:
                logger.warning(
                    f"Skipping route '{route_name}' due to config error: {e}"
                )
                continue

            # Get profile config to find model/dim
            profiles_cfg = config.get("embeddings", {}).get("profiles", {})
            resolved_profile_cfg = profiles_cfg.get(profile_name, {})

            # Reuse embedding if possible
            if profile_name in embedding_cache:
                query_vector, query_norm = embedding_cache[profile_name]
            else:
                resolved_model = (
                    resolved_profile_cfg.get("model") or embedding_model_name()
                )
                resolved_dim = resolved_profile_cfg.get("dim") or embedding_model_dim()
                if resolved_model in HASH_MODELS:
                    resolved_dim = 64

                logger.debug(
                    f"Embedding query for route='{route_name}' (profile='{profile_name}'): model='{resolved_model}'"
                )

                backend = build_embedding_backend(resolved_model, dim=resolved_dim)
                query_vector = np.array(backend.embed_queries([query])[0])
                query_norm = _norm(query_vector)
                embedding_cache[profile_name] = (query_vector, query_norm)

            # Search DB
            try:
                scored_objs = _score_candidates(
                    query_vector,
                    query_norm,
                    db.iter_embeddings(table_name=index_name),
                    query_text=query,
                    repo_root=repo,
                )

                # Convert to dicts for fusion
                results_by_route[route_name] = [
                    {**asdict(r), "slice_id": r.span_hash} for r in scored_objs
                ]

            except ValueError:
                logger.warning(
                    f"Query search against '{index_name}' failed. Skipping this route."
                )
                continue

    finally:
        db.close()

    # 4. Fuse
    fused_dicts = fuse_scores(results_by_route, route_weights)

    # Optional: Graph Expansion
    if config.get("rag", {}).get("graph", {}).get("enable_expansion", False):
        from llmc.rag.graph_expand import expand_with_graph

        fused_dicts = expand_with_graph(fused_dicts, repo, config)

    top_dicts = fused_dicts[:limit]

    # 5. Reconstruct Objects
    top_results = []
    for d in top_dicts:
        # Remove 'slice_id' and internal fusion/expansion metadata fields
        d_clean = {
            k: v for k, v in d.items() 
            if k != "slice_id" and not k.startswith("_")
        }
        # Path object is preserved by asdict
        top_results.append(SpanSearchResult(**d_clean))

    if debug:
        top_results = _enrich_debug_info(top_results, repo, db_path)
        # Assign ranks and attach routing info
        new_results = []
        for i, r in enumerate(top_results):
            d_info = r.debug_info or {}
            search_info = d_info.get("search", {})
            search_info["rank"] = i + 1
            if route_decision:
                search_info["routing"] = route_decision
                search_info["multi_route_fanout"] = (
                    routes_to_query if len(routes_to_query) > 1 else None
                )
                # Add target_index based on primary route if not multi-route
                if not (len(routes_to_query) > 1):  # If single route
                    try:
                        _, primary_index_name = resolve_route(
                            primary_route, "query", repo
                        )
                        search_info["target_index"] = primary_index_name
                    except ConfigError:
                        logger.warning(
                            f"Could not resolve primary route index for debug info: {primary_route}"
                        )

            new_results.append(
                SpanSearchResult(
                    span_hash=r.span_hash,
                    path=r.path,
                    symbol=r.symbol,
                    kind=r.kind,
                    start_line=r.start_line,
                    end_line=r.end_line,
                    score=r.score,
                    summary=r.summary,
                    normalized_score=r.normalized_score,
                    debug_info={**d_info, "search": search_info},
                )
            )
        top_results = new_results

    return top_results
