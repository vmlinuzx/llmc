from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections.abc import Iterable, Sequence

from .config import (
    index_path_for_read,
    is_query_routing_enabled,
    load_config,
    embedding_model_name,
    embedding_model_dim,
)
from .database import Database
from .embeddings import build_embedding_backend, HASH_MODELS
from .utils import find_repo_root
from llmc.routing.query_type import classify_query
import logging

logger = logging.getLogger(__name__)


def _norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(v * v for v in vector))


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _unpack_vector(blob: bytes) -> List[float]:
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


def _filename_boost(query: str, path_str: str) -> float:
    """Calculate score boost for filename matches."""
    if not query:
        return 0.0
    q = query.strip().lower()
    import os
    basename = os.path.basename(path_str).lower()
    stem, _ = os.path.splitext(basename)
    
    if q == basename:
        return 0.20  # Huge boost for exact match
    if q == stem:
        return 0.15  # Big boost for stem match
    if q in basename:
        return 0.05  # Small boost for partial match
    return 0.0


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
    debug_info: Optional[Dict[str, Any]] = field(default=None)


def _score_candidates(
    query_vector: Sequence[float],
    query_norm: float,
    rows: Iterable,
    query_text: str | None = None,
) -> List[SpanSearchResult]:
    results: List[SpanSearchResult] = []
    for row in rows:
        vector = _unpack_vector(row["vec"])
        vector_norm = _norm(vector)
        if query_norm == 0.0 or vector_norm == 0.0:
            continue
        similarity = _dot(query_vector, vector) / (query_norm * vector_norm)
        
        if query_text:
            similarity += _filename_boost(query_text, row["file_path"])

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
            )
        )
    results.sort(key=lambda item: item.score, reverse=True)
    return results


def _enrich_debug_info(
    results: List[SpanSearchResult],
    repo_root: Path,
    db_path: Path,
) -> List[SpanSearchResult]:
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
                rows = db.conn.execute(
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
                        "evidence_count": len(json.loads(row["evidence"])) if row["evidence"] else 0,
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
            from .schema import SchemaGraph
            graph = SchemaGraph.load(graph_path)
            
            # Index entities by span_hash or fuzzy location
            # For now, let's try to match by file path and line overlap
            # Optimization: Pre-index graph entities by file path
            entities_by_file = {}
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
            rels_by_src = {}
            rels_by_dst = {}
            for rel in graph.relations:
                rels_by_src.setdefault(rel.src, []).append(rel)
                rels_by_dst.setdefault(rel.dst, []).append(rel)

            for res in results:
                # Try to find matching entity
                res_path_str = str(res.path.relative_to(repo_root)) if res.path.is_absolute() else str(res.path)
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
                        except:
                            continue

                    # Check overlap
                    if not (e_end < res.start_line or e_start > res.end_line):
                        matched_ent = ent
                        break
                
                if matched_ent:
                    # Gather neighbors
                    parents = [] # Logic to find parents (containers) is implicit in AST or naming usually
                    children = []
                    related_code = []
                    related_tests = []
                    related_docs = []

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
                "rank": -1, # To be filled by caller or implicit order
                "score": res.score,
                "embedding_similarity": res.score,
                # No reranker in this simple search pipeline
            },
            "enrichment": enrich_map.get(res.span_hash, None),
            "graph": graph_map.get(res.span_hash, None),
            "provenance": {
                "kind": res.kind,
                # Last commit could be fetched via git if slow is ok, skipping for speed
            }
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
                debug_info=debug
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
    tool_context: Optional[Dict[str, Any]] = None,
) -> List[SpanSearchResult]:
    """Execute a simple cosine-similarity search over the local `.rag` index."""
    repo = repo_root or find_repo_root()
    db_path = index_path_for_read(repo)
    if not db_path.exists():
        raise FileNotFoundError(
            f"No embedding index found at {db_path}. Run `python -m tools.rag.cli index` and `embed --execute` first."
        )

    # Routing logic
    route_decision = None
    target_profile = None
    target_index = "embeddings"
    
    # Defaults
    resolved_model = model_override
    resolved_dim = None

    if is_query_routing_enabled(repo):
        classification = classify_query(query, tool_context=tool_context)
        route_name = classification["route_name"]
        route_decision = classification
        
        if logger.isEnabledFor(logging.INFO):
            logger.info(
                "Query routing: route=%s confidence=%.2f reasons=%s query_hash=%s",
                route_name,
                classification["confidence"],
                classification["reasons"],
                hash(query)
            )
        
        config = load_config(repo)
        # Resolve route -> profile -> index
        # Assuming embeddings.routes.<name> exists
        routes_cfg = config.get("embeddings", {}).get("routes", {})
        route_cfg = routes_cfg.get(route_name, {})
        
        if not route_cfg:
            # Fallback to docs if route not found
            route_name = "docs"
            route_cfg = routes_cfg.get("docs", {"profile": "default_docs", "index": "embeddings"})
            if route_decision:
                route_decision["fallback"] = "route_not_found"

        target_index = route_cfg.get("index", "embeddings")
        profile_name = route_cfg.get("profile", "default_docs")
        
        # Get profile config to find model/dim
        profiles_cfg = config.get("embeddings", {}).get("profiles", {})
        profile_cfg = profiles_cfg.get(profile_name, {})
        
        if not model_override:
            resolved_model = profile_cfg.get("model")
            resolved_dim = profile_cfg.get("dim")

    # Fallback to defaults if not routed or model not found
    if not resolved_model:
        resolved_model = embedding_model_name()
    if not resolved_dim:
        resolved_dim = embedding_model_dim()
        if resolved_model in HASH_MODELS:
            resolved_dim = 64

    backend = build_embedding_backend(resolved_model, dim=resolved_dim)
    query_vector = backend.embed_queries([query])[0]
    query_norm = _norm(query_vector)

    db = Database(db_path)
    try:
        # Pass table_name to iter_embeddings
        scored = _score_candidates(
            query_vector, 
            query_norm, 
            db.iter_embeddings(table_name=target_index), 
            query_text=query
        )
    except ValueError:
         # Fallback to default table if target_index is invalid/empty
         scored = _score_candidates(
            query_vector, 
            query_norm, 
            db.iter_embeddings(table_name="embeddings"), 
            query_text=query
        )
    finally:
        db.close()
    
    top_results = scored[:limit]
    
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
                search_info["target_index"] = target_index
            
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
                    debug_info={**d_info, "search": search_info}
                )
            )
        top_results = new_results

    return top_results

