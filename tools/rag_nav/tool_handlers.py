"""
Phase 3 — Patch P3: Minimal graph-backed results for RAG Nav tools.

Reads `.llmc/rag_graph.json` under the provided repo_root and returns real items
for search/where-used/lineage using lightweight heuristics. No DB writes, no
advanced scoring — just enough to satisfy tests with deterministic behavior.
"""

from __future__ import annotations

from collections.abc import Iterable
import json
import logging
import os
from pathlib import Path
from typing import Any

# --- Context Gateway integration imports ---
from tools.rag.config import load_rerank_weights
from tools.rag.db_fts import RagDbNotFound, fts_search
from tools.rag.graph_index import (
    GraphNotFound as IndexGraphNotFound,
    lineage_files as lineage_files_from_index,
    load_indices as load_graph_indices,
    where_used_files as where_used_files_from_index,
)
from tools.rag.graph_stitch import Neighbor, expand_search_items
from tools.rag.locator import identify_symbol_at_line
from tools.rag.rerank import RerankHit, rerank_hits
from tools.rag_nav.gateway import compute_route as _compute_route
from tools.rag_nav.models import (
    EnrichmentData,
    LineageItem,
    LineageResult,
    SearchItem,
    SearchResult,
    Snippet,
    SnippetLocation,
    SourceTag,
    WhereUsedItem,
    WhereUsedResult,
)

# -------------------------------------------

_enrich_log = logging.getLogger("llmc.enrich")


_GRAPH_REL_PATH = os.path.join(".llmc", "rag_graph.json")
_SUPPORTED_EDGE_TYPES = {"CALLS", "IMPORTS", "READS", "WRITES", "USES"}


def _rag_graph_path(repo_root: Path | str) -> Path:
    """Internal helper: path to the RAG Nav graph JSON."""
    return Path(repo_root) / ".llmc" / "rag_graph.json"


def _attach_graph_enrichment(repo_root: Path | str, items: list[Any]):
    """Attach enrichment data from loaded graph nodes to result items.

    Args:
        repo_root: Repository root path
        items: List of SearchItem, WhereUsedItem, or LineageItem objects

    Returns:
        The modified list of items with enrichment attached where found.
    """
    nodes, _ = _load_graph(repo_root)
    if not nodes:
        return items

    # Index nodes by file path for fast lookup (legacy/fallback)
    nodes_by_path: dict[str, list[dict]] = {}
    # Also index by ID for AST lookup
    nodes_by_id: dict[str, dict] = {}

    for n in nodes:
        p = _node_path(n)
        if p:
            nodes_by_path.setdefault(p, []).append(n)

        nid = _node_name(n)
        # Normalize ID: strip prefix if present
        if nid.startswith("sym:"):
            nid = nid[4:]
        elif nid.startswith("type:"):
            nid = nid[5:]
        nodes_by_id[nid] = n

    # Cache for file content to avoid re-reading per item
    source_cache = {}

    for item in items:
        if not item.file:
            continue

        best_node = None

        # Strategy 1: Fuzzy AST Linking (Resilient to line shifts)
        # Only works if we have line number info
        if item.snippet and item.snippet.location:
            # Read file content
            if item.file not in source_cache:
                try:
                    source_cache[item.file] = (Path(repo_root) / item.file).read_text(
                        errors="ignore"
                    )
                except Exception:
                    source_cache[item.file] = None

            source = source_cache[item.file]
            if source:
                sl = item.snippet.location.start_line
                # Find the symbol name at this line in the *current* file
                symbol_id = identify_symbol_at_line(source, sl)
                # DEBUG
                # print(f"DEBUG: file={item.file} line={sl} symbol_id={symbol_id}")
                if symbol_id:
                    # Construct graph ID: {stem}.{symbol}
                    # This matches schema.py's ID generation
                    stem = Path(item.file).stem
                    graph_id = f"{stem}.{symbol_id}"

                    # DEBUG
                    # print(f"DEBUG: constructed graph_id={graph_id}")
                    # print(f"DEBUG: nodes_by_id keys={list(nodes_by_id.keys())[:5]}")

                    if graph_id in nodes_by_id:
                        best_node = nodes_by_id[graph_id]

        # Strategy 2: Legacy Line Overlap (Fallback)
        if not best_node:
            candidates = nodes_by_path.get(item.file, [])
            if item.snippet and item.snippet.location:
                sl = item.snippet.location.start_line
                el = item.snippet.location.end_line

                for node in candidates:
                    n_start, n_end = _node_span(node)
                    if n_start is not None and n_end is not None:
                        # Check for overlap or containment
                        if not (el < n_start or sl > n_end):
                            best_node = node
                            break

        if best_node:
            metadata = best_node.get("metadata")
            if metadata:
                enrich = EnrichmentData(
                    summary=metadata.get("summary"), usage_guide=metadata.get("usage_guide")
                )
                if enrich.summary or enrich.usage_guide:
                    item.enrichment = enrich

    return items


def _graph_path(repo_root: Path | str) -> Path:
    """
    Compatibility wrapper for the legacy schema graph path.

    Tests for the Phase 2 builder expect this function to return the
    path used by tools.rag.build_graph_for_repo (schema_graph.json).
    """
    from tools.rag import _graph_path as _core_graph_path

    return _core_graph_path(Path(repo_root))


def _load_graph(repo_root: Path | str) -> tuple[list[dict], list[dict]]:
    """Return (nodes, edges). If missing or invalid, return ([], [])."""
    path = _rag_graph_path(repo_root)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        nodes = data.get("nodes") or data.get("entities") or []
        edges = data.get("edges") or []

        # Allow consuming schema_graph artifacts by projecting relations into edges.
        # Try three formats:
        # 1. Top-level "relations" key (SchemaGraph.to_dict() format)
        # 2. Nested "schema_graph.relations"
        # 3. Already have "edges"
        if not edges:
            rels = data.get("relations") or []  # Format 1: top-level relations
            if not rels and isinstance(data.get("schema_graph"), dict):
                rels = data["schema_graph"].get("relations") or []  # Format 2: nested

            if isinstance(rels, list) and rels:
                edges = [
                    {
                        "type": str(r.get("edge") or "").upper(),
                        "source": r.get("src") or r.get("from") or "",
                        "target": r.get("dst") or r.get("to") or "",
                    }
                    for r in rels
                ]
        if not isinstance(nodes, list) or not isinstance(edges, list):
            return [], []
        return nodes, edges
    except Exception:
        return [], []


def _node_name(n: dict) -> str:
    return str(n.get("name") or n.get("id") or "")


def _node_path(n: dict) -> str:
    return str(n.get("path") or n.get("file") or n.get("filepath") or "")


def _node_span(n: dict) -> tuple[int | None, int | None]:
    span = n.get("span") or n.get("loc") or {}
    start = (
        span.get("start_line") or span.get("start") or span.get("line_start") or n.get("start_line")
    )
    end = span.get("end_line") or span.get("end") or span.get("line_end") or n.get("end_line")
    try:
        start_i = int(start) if start is not None else None
        end_i = int(end) if end is not None else None
        return start_i, end_i
    except Exception:
        return None, None


def _read_snippet(
    repo_root: str, path: str, start_line: int | None, end_line: int | None
) -> Snippet:
    """Read file and slice [start_line, end_line]. Lines are 1-based, inclusive."""
    abspath = os.path.join(repo_root, path) if path else ""
    text = ""
    sl = start_line or 1
    el = end_line or (sl + 15)
    if os.path.isfile(abspath):
        try:
            with open(abspath, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            total = len(lines)
            sl = max(1, min(sl, total if total else 1))
            el = max(sl, min(el, total if total else sl))
            text = "".join(lines[sl - 1 : el])
        except Exception:
            text = ""
    return Snippet(text=text, location=SnippetLocation(path=path or "", start_line=sl, end_line=el))


def _max_n(max_results: int | None, default: int = 20) -> int:
    try:
        if max_results is None:
            return default
        return max(1, int(max_results))
    except Exception:
        return default


def _index_nodes(nodes: list[dict]) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    by_id: dict[str, dict] = {}
    by_name_lower: dict[str, list[dict]] = {}
    for n in nodes:
        nid = str(n.get("id") or _node_name(n))
        by_id[nid] = n
        nm = _node_name(n).lower()
        if nm:
            by_name_lower.setdefault(nm, []).append(n)
    return by_id, by_name_lower


def _match_nodes(nodes: list[dict], query: str) -> list[dict]:
    q = (query or "").lower().strip()
    if not q:
        return []
    out: list[dict] = []
    seen: set[int] = set()
    for i, n in enumerate(nodes):
        name = _node_name(n).lower()
        path = _node_path(n).lower()
        if q in name or q in path:
            if i not in seen:
                seen.add(i)
                out.append(n)
    return out


def _resolve_symbol_nodes(nodes: list[dict], symbol: str) -> list[dict]:
    if not symbol:
        return []
    q = symbol.lower()
    out: list[dict] = []
    for n in nodes:
        name = _node_name(n).lower()
        if name.endswith(q) or q in name:
            out.append(n)
    return out


def build_graph_for_repo(repo_root: Path | str):
    """
    Build both the legacy schema_graph artifact and a nav-ready rag_graph.json.

    This function:
      - Delegates to tools.rag.build_graph_for_repo to generate a simple
        schema_graph.json and persist index status.
      - Uses the Phase 2 schema graph builder to construct an AST-only graph
        and projects it into a lightweight nodes/edges structure consumed by
        the search/where-used/lineage helpers in this module.
    """
    from tools.rag import build_graph_for_repo as _core_build_graph_for_repo
    from tools.rag.schema import build_graph_for_repo as _schema_build_graph_for_repo

    repo_root_path = Path(repo_root)

    # First, build the legacy graph + status so existing callers and tests
    # that inspect schema_graph.json continue to work.
    status = _core_build_graph_for_repo(repo_root_path)

    # Phase 2 Integration:
    # Build the enriched schema graph. This replaces the manual AST-only scan below
    # as the source of truth for rag_graph.json.
    try:
        enriched_graph = build_enriched_schema_graph(repo_root_path)
        # Since build_enriched_schema_graph already saves the file, we can return status early
        # However, to maintain compatibility with the existing function structure which
        # reads rag_graph.json later if needed, we can let it proceed or just return.
        # For safety, let's return status now as the graph is built.
        return status
    except Exception as e:
        # Fallback to legacy behavior if enrichment fails (e.g. no DB)
        _enrich_log.warning(f"Enriched graph build failed, falling back to AST-only: {e}")

    # Next, build an AST-only schema graph (no DB required) and derive a
    # minimal nodes/edges representation for RAG Nav.
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    try:
        schema_graph = _schema_build_graph_for_repo(repo_root_path, require_enrichment=False)
    except Exception:
        schema_graph = None

    if schema_graph and schema_graph.entities:
        # Preferred path: use the Phase 2 schema graph if we have entities.
        for entity in schema_graph.entities:
            path = entity.file_path or entity.path
            if isinstance(path, str) and ":" in path and not entity.file_path:
                # Strip line-range suffix if present (e.g., "foo.py:10-20")
                path = path.split(":", 1)[0]
            span: dict[str, int] = {}
            if entity.start_line is not None:
                span["start_line"] = int(entity.start_line)
            if entity.end_line is not None:
                span["end_line"] = int(entity.end_line)

            node: dict[str, Any] = {
                "id": entity.id,
                "name": entity.id,
                "path": path or "",
            }
            if span:
                node["span"] = span
            nodes.append(node)

        for relation in schema_graph.relations:
            edges.append(
                {
                    "type": str(relation.edge or "").upper(),
                    "source": relation.src,
                    "target": relation.dst,
                }
            )
    else:
        # Fallback path: simple text-based scan over .py files that tolerates
        # syntactically invalid Python (e.g., leading indentation).
        def _iter_py_files(root: Path) -> Iterable[Path]:
            for path in root.rglob("*.py"):
                # Skip common junk directories.
                if any(
                    part in {".git", ".venv", "venv", "__pycache__", "node_modules"}
                    for part in path.parts
                ):
                    continue
                yield path

        # First pass: collect defined symbol names by scanning for def/class.
        defined_symbols: set[str] = set()
        file_paths: list[Path] = []
        for file_path in _iter_py_files(repo_root_path):
            file_paths.append(file_path)
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line in text.splitlines():
                stripped = line.lstrip()
                if stripped.startswith("def ") or stripped.startswith("class "):
                    name_part = stripped.split(" ", 1)[1]
                    name = name_part.split("(", 1)[0].split(":", 1)[0].strip()
                    if name:
                        defined_symbols.add(name)

        # Create file-level nodes so where-used results can report file paths.
        for file_path in file_paths:
            rel_path = str(file_path.relative_to(repo_root_path))
            nodes.append(
                {
                    "id": rel_path,
                    "name": rel_path,
                    "path": rel_path,
                }
            )

        # Create symbol definition nodes.
        for file_path in file_paths:
            rel_path = str(file_path.relative_to(repo_root_path))
            try:
                lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for idx, line in enumerate(lines, start=1):
                stripped = line.lstrip()
                if stripped.startswith("def ") or stripped.startswith("class "):
                    name_part = stripped.split(" ", 1)[1]
                    name = name_part.split("(", 1)[0].split(":", 1)[0].strip()
                    if name in defined_symbols:
                        nodes.append(
                            {
                                "id": name,
                                "name": name,
                                "path": rel_path,
                                "span": {"start_line": idx, "end_line": idx},
                            }
                        )

        # Second pass: add simple CALLS edges based on `name(` occurrences.
        for file_path in file_paths:
            rel_path = str(file_path.relative_to(repo_root_path))
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for sym in defined_symbols:
                token = f"{sym}("
                if token in text:
                    # Edge from caller file -> callee symbol (where-used).
                    edges.append(
                        {
                            "type": "CALLS",
                            "source": rel_path,  # file-level node id
                            "target": sym,  # symbol-level node id
                        }
                    )
                    # Symmetric edge from symbol -> caller file (lineage downstream).
                    edges.append(
                        {
                            "type": "CALLS",
                            "source": sym,
                            "target": rel_path,
                        }
                    )

    rag_path = _rag_graph_path(repo_root_path)
    rag_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "nodes": nodes,
        "edges": edges,
    }
    try:
        rag_path.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        # Writing the nav graph is best-effort; status + legacy graph already exist.
        pass

    return status


# ============================================================================
# Phase 2: Enriched Schema Graph Builder
# ============================================================================


def _build_base_structural_schema_graph(repo_root: Path) -> Any:
    """Loads/builds the purely structural graph from AST analysis.

    Internal helper for Phase 2. Reuses existing Phase 2 logic.
    """
    from tools.rag.schema import build_graph_for_repo as _schema_build_graph_for_repo

    # Force require_enrichment=False to get the raw AST graph
    return _schema_build_graph_for_repo(repo_root, require_enrichment=False)


def _save_schema_graph(repo_root: Path, graph: Any):
    """Saves the SchemaGraph to disk.

    Internal helper for Phase 2.
    """
    graph_path = repo_root / ".llmc" / "rag_graph.json"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    # Use graph.save if available, else dump manually
    if hasattr(graph, "save"):
        graph.save(graph_path)
    else:
        with open(graph_path, "w") as f:
            json.dump(graph.to_dict(), f, indent=2)


def build_enriched_schema_graph(repo_root: Path) -> Any:
    """
    Builds the SchemaGraph and enriches its entities with data from the
    enrichment database.
    """
    from tools.rag.enrichment_db_helpers import load_enrichment_data

    # 1. Build the base structural graph
    base_graph = _build_base_structural_schema_graph(repo_root)

    # 2. Load all enrichment data
    enrichments_by_span = load_enrichment_data(repo_root)

    # 3. Build Spatial Index: (normalized_path, start_line) -> EnrichmentRecord
    # This bridges the gap between AST (Graph) and Content Hash (DB).
    enrich_by_loc: dict[tuple[str, int], Any] = {}

    # load_enrichment_data now returns Dict[span_hash, List[EnrichmentRecord]]
    # We iterate the lists of records.
    for records in enrichments_by_span.values():
        for record in records:
            if record.file_path and record.start_line is not None:
                # Normalize path relative to repo_root
                try:
                    p = Path(record.file_path)
                    if p.is_absolute():
                        norm_p = str(p.relative_to(repo_root))
                    else:
                        norm_p = str(p)
                except ValueError:
                    norm_p = str(record.file_path)

                enrich_by_loc[(norm_p, record.start_line)] = record

    # 4. Iterate through graph entities and merge metadata
    enriched_count = 0

    if hasattr(base_graph, "entities"):
        for entity in base_graph.entities:
            if not entity.file_path or entity.start_line is None:
                continue

            # Normalize entity path (AST paths are usually absolute in this pipeline)
            try:
                p = Path(entity.file_path)
                if p.is_absolute():
                    norm_entity_path = str(p.relative_to(repo_root))
                else:
                    norm_entity_path = str(p)
            except ValueError:
                norm_entity_path = entity.file_path

            # Update entity path to be relative in the export
            entity.file_path = norm_entity_path

            # Match by Location
            key = (norm_entity_path, entity.start_line)
            enrich = enrich_by_loc.get(key)

            if enrich:
                _attach_enrichment_to_entity(entity, enrich)
                enriched_count += 1

    print(
        f"    📊 Enrichment integration: {enriched_count}/{len(base_graph.entities)} entities enriched."
    )

    # 4. Save the enriched graph
    _save_schema_graph(repo_root, base_graph)

    return base_graph


def _attach_enrichment_to_entity(entity: Any, enrich: Any) -> None:
    """Internal helper to attach enrichment fields to entity metadata.

    Args:
        entity: Entity to enrich
        enrich: EnrichmentRecord with metadata
    """
    # Parse JSON fields if they're stored as strings
    import json

    def safe_json_load(value: str | None) -> list | None:
        if not value:
            return None
        try:
            return json.loads(value) if isinstance(value, str) else value
        except (json.JSONDecodeError, TypeError):
            return None

    # Attach all enrichment fields
    if enrich.summary:
        entity.metadata["summary"] = enrich.summary

    # Map usage_guide (Record) -> usage_guide (Metadata) or usage_snippet (Metadata)
    # The Record has 'usage_guide' populated from DB 'usage_snippet'.
    if enrich.usage_guide:
        entity.metadata["usage_guide"] = enrich.usage_guide
        entity.metadata["usage_snippet"] = enrich.usage_guide  # redundant but safe

    # Additional fields (if available in record)
    # Note: EnrichmentRecord currently only has summary/usage_guide populated by load_enrichment_data
    # but we should be ready for others if they are added.

    # Always store symbol/span_hash for downstream tools.
    if getattr(enrich, "symbol", None):
        entity.metadata["symbol"] = enrich.symbol
    if enrich.span_hash:
        entity.metadata["span_hash"] = enrich.span_hash


# --- Fallback helpers (local scan) ---------------------------------------------
def _iter_repo_py_files(repo_root):
    import os

    skip_dirs = {
        ".git",
        ".llmc",
        ".trash",
        "__pycache__",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
    }
    for root, dirs, files in os.walk(str(repo_root)):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for name in files:
            if name.endswith(".py"):
                rel = os.path.relpath(os.path.join(root, name), str(repo_root))
                yield rel


def _grep_snippets(repo_root, needle, max_items):
    items = []
    try:
        for rel in _iter_repo_py_files(repo_root):
            abspath = os.path.join(str(repo_root), rel)
            try:
                with open(abspath, encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                for i, line in enumerate(lines, start=1):
                    if needle in line:
                        sl = max(1, i - 2)
                        el = min(len(lines), i + 2)
                        text = "".join(lines[sl - 1 : el])
                        items.append((rel, sl, el, text))
                        if len(items) >= max_items:
                            return items
            except Exception:
                continue
    except Exception:
        pass
    return items


def _neighbors_to_items(neigh: list[Neighbor]) -> list[SearchItem]:
    items: list[SearchItem] = []
    for n in neigh:
        loc = SnippetLocation(path=n.path, start_line=1, end_line=1)
        items.append(SearchItem(file=n.path, snippet=Snippet(text="", location=loc)))
    return items


def tool_rag_search(repo_root, query: str, limit: int | None = None) -> SearchResult:
    """Search using DB FTS + reranker + 1-hop graph stitch when route allows RAG."""
    route = _compute_route(Path(repo_root))
    repo_root_path = Path(repo_root)
    max_results = _max_n(limit, default=20)
    source: SourceTag = "RAG_GRAPH" if route.use_rag else "LOCAL_FALLBACK"

    if route.use_rag:
        try:
            hits = fts_search(repo_root_path, query, limit=max(100, max_results * 3))
            rr_hits = [
                RerankHit(
                    file=h.file,
                    start_line=h.start_line,
                    end_line=h.end_line,
                    text=h.text,
                    score=h.score,
                )
                for h in hits
            ]
            weights = load_rerank_weights(repo_root_path)
            ranked = rerank_hits(query, rr_hits, top_k=max_results, weights=weights)
            items: list[SearchItem] = [
                SearchItem(
                    file=h.file,
                    snippet=Snippet(
                        text=h.text,
                        location=SnippetLocation(
                            path=h.file, start_line=h.start_line, end_line=h.end_line
                        ),
                    ),
                )
                for h in ranked
            ]
            truncated = len(hits) > len(items)

            # P9c: graph-stitch 1-hop neighbors to fill remaining budget.
            remaining = max(0, max_results - len(items))
            if remaining > 0:
                try:
                    res = expand_search_items(
                        repo_root_path, items, max_expansion=min(remaining, max_results), hops=1
                    )
                    if isinstance(res, tuple):
                        _, neigh = res
                        neighbor_items = _neighbors_to_items(neigh)
                        seen_files = {it.file for it in items}
                        for ni in neighbor_items:
                            if len(items) >= max_results:
                                break
                            if ni.file in seen_files:
                                continue
                            seen_files.add(ni.file)
                            items.append(ni)
                except Exception:
                    pass

            res = SearchResult(
                query=query,
                items=items[:max_results],
                truncated=truncated if "truncated" in locals() else False,
                source=source,
                freshness_state=getattr(route, "freshness_state", "UNKNOWN"),
            )
            # Phase 3: Attach graph enrichment if available
            res.items = _attach_graph_enrichment(repo_root, res.items)

            return _maybe_attach_enrichment_search(repo_root, res)
        except (RagDbNotFound, RuntimeError):
            source = "LOCAL_FALLBACK"

    # Fallback: local grep over .py files when no RAG route or DB issues.
    grep_hits = _grep_snippets(repo_root, query, max_results)
    fallback_items: list[SearchItem] = []
    for rel, sl, el, text in grep_hits:
        fallback_items.append(
            SearchItem(
                file=rel,
                snippet=Snippet(
                    text=text,
                    location=SnippetLocation(path=rel, start_line=sl, end_line=el),
                ),
            )
        )
    res = SearchResult(
        query=query,
        items=fallback_items,
        truncated=False,
        source=source,
        freshness_state=getattr(route, "freshness_state", "UNKNOWN"),
    )
    # Phase 3: Attach graph enrichment if available (even for fallback search if graph exists)
    res.items = _attach_graph_enrichment(repo_root, res.items)

    return _maybe_attach_enrichment_search(repo_root, res)


def tool_rag_where_used(repo_root, symbol: str, limit: int | None = None) -> WhereUsedResult:
    """Where-used query using graph indices when the Context Gateway allows RAG."""
    route = _compute_route(Path(repo_root))
    max_results = _max_n(limit, default=50)
    source: SourceTag = "RAG_GRAPH" if getattr(route, "use_rag", False) else "LOCAL_FALLBACK"
    if getattr(route, "use_rag", False):
        try:
            indices = load_graph_indices(Path(repo_root))
            files = where_used_files_from_index(indices, symbol, limit=max_results)
            items: list[WhereUsedItem] = []
            for path in files[:max_results]:
                loc = SnippetLocation(path=path, start_line=1, end_line=1)
                snippet = Snippet(text="", location=loc)
                items.append(WhereUsedItem(file=path, snippet=snippet))
            res = WhereUsedResult(
                symbol=symbol,
                items=items,
                truncated=len(files) > len(items),
                source=source,
                freshness_state=route.freshness_state,
            )
            res.items = _attach_graph_enrichment(repo_root, res.items)
            return _maybe_attach_enrichment_where_used(repo_root, res)
        except (IndexGraphNotFound, Exception):
            # Any graph loading/indexing issue should route to the local fallback.
            source = "LOCAL_FALLBACK"

    # Fallback: grep symbol usages when RAG is unavailable or index loading failed.
    grep_hits = _grep_snippets(repo_root, symbol, max_results)
    items = [
        WhereUsedItem(
            file=rel,
            snippet=Snippet(
                text=text,
                location=SnippetLocation(path=rel, start_line=sl, end_line=el),
            ),
        )
        for rel, sl, el, text in grep_hits
    ]
    res = WhereUsedResult(
        symbol=symbol,
        items=items,
        truncated=False,
        source=source,
        freshness_state=route.freshness_state,
    )
    res.items = _attach_graph_enrichment(repo_root, res.items)
    return _maybe_attach_enrichment_where_used(repo_root, res)


def tool_rag_lineage(
    repo_root,
    symbol: str,
    direction: str,
    max_results: int | None = None,
) -> LineageResult:
    """Lineage query using graph indices when the Context Gateway allows RAG."""
    route = _compute_route(Path(repo_root))
    limit = _max_n(max_results, default=50)
    dir_norm = (direction or "downstream").lower().strip()
    normalized_direction = "upstream" if dir_norm in ("upstream", "callers") else "downstream"
    source: SourceTag = "RAG_GRAPH" if getattr(route, "use_rag", False) else "LOCAL_FALLBACK"

    if getattr(route, "use_rag", False):
        try:
            indices = load_graph_indices(Path(repo_root))
            files = lineage_files_from_index(
                indices,
                symbol,
                direction=normalized_direction,
                limit=limit,
            )
            items: list[LineageItem] = []
            for path in files[:limit]:
                loc = SnippetLocation(path=path, start_line=1, end_line=1)
                snippet = Snippet(text="", location=loc)
                items.append(LineageItem(file=path, snippet=snippet))
            res = LineageResult(
                symbol=symbol,
                direction=normalized_direction,
                items=items,
                truncated=len(files) > len(items),
                source=source,
                freshness_state=route.freshness_state,
            )
            res.items = _attach_graph_enrichment(repo_root, res.items)
            return _maybe_attach_enrichment_lineage(repo_root, res)
        except (IndexGraphNotFound, Exception):
            # Any graph loading/indexing issue should route to the local fallback.
            source = "LOCAL_FALLBACK"

    # Fallback: naive grep for callsites "symbol(" as pseudo-lineage.
    grep_hits = _grep_snippets(repo_root, f"{symbol}(", limit)
    fallback_items: list[LineageItem] = []
    for rel, sl, el, text in grep_hits:
        fallback_items.append(
            LineageItem(
                file=rel,
                snippet=Snippet(
                    text=text,
                    location=SnippetLocation(path=rel, start_line=sl, end_line=el),
                ),
            )
        )
    res = LineageResult(
        symbol=symbol,
        direction=normalized_direction,
        items=fallback_items,
        truncated=False,
        source=source,
        freshness_state=route.freshness_state,
    )
    res.items = _attach_graph_enrichment(repo_root, res.items)
    return _maybe_attach_enrichment_lineage(repo_root, res)


def tool_rag_stats(repo_root: Path | str) -> dict[str, Any]:
    """Return statistics about the RAG graph and enrichment coverage."""
    nodes, _ = _load_graph(repo_root)
    total_nodes = len(nodes)
    enriched_nodes = sum(1 for n in nodes if n.get("metadata", {}).get("summary"))

    return {
        "total_nodes": total_nodes,
        "enriched_nodes": enriched_nodes,
        "coverage_pct": (enriched_nodes / total_nodes * 100) if total_nodes > 0 else 0.0,
    }


def _enrichment_enabled() -> bool:
    flag = str(os.getenv("LLMC_ENRICH", "")).lower()
    attach = str(os.getenv("LLMC_ENRICH_ATTACH", "")).lower()
    return flag in {"1", "true", "yes", "on"} or attach in {"1", "true", "yes"}


def _enrichment_max_chars() -> int | None:
    raw = os.getenv("LLMC_ENRICH_MAX_CHARS")
    if raw and raw.isdigit():
        try:
            value = int(raw)
            return value if value > 0 else None
        except Exception:
            return None
    return None


def _maybe_attach_enrichment_search(repo_root: str, res: SearchResult) -> SearchResult:
    if not _enrichment_enabled():
        return res
    try:
        from tools.rag_nav.enrichment import (
            EnrichStats,
            SqliteEnrichmentStore,
            attach_enrichments_to_search_result,
            discover_enrichment_db,
        )

        db_env = os.getenv("LLMC_ENRICH_DB")
        db_path: Path | None
        if not db_env or not Path(db_env).exists():
            db_path = discover_enrichment_db(Path(repo_root), getattr(res, "items", None))
        else:
            db_path = Path(db_env)
        if not db_path or not db_path.exists():
            return res

        stats = EnrichStats()
        store = SqliteEnrichmentStore(db_path)
        max_chars = _enrichment_max_chars()
        res = attach_enrichments_to_search_result(
            res, store, max_snippets=1, max_chars=max_chars, stats=stats
        )

        if str(os.getenv("LLMC_ENRICH_LOG", "")).lower() in {"1", "true", "yes"}:
            _enrich_log.info(
                "enrich attach (search): db=%s items=%d attached=%d line=%d path=%d truncated=%d",
                db_path,
                len(getattr(res, "items", []) or []),
                stats.snippets_attached,
                stats.line_matches,
                stats.path_matches,
                stats.fields_truncated,
            )
    except Exception:
        # Enrichment is best-effort; never break core search behavior.
        return res
    return res


def _maybe_attach_enrichment_where_used(repo_root: str, res: WhereUsedResult) -> WhereUsedResult:
    if not _enrichment_enabled():
        return res
    try:
        from tools.rag_nav.enrichment import (
            EnrichStats,
            SqliteEnrichmentStore,
            attach_enrichments_to_where_used,
            discover_enrichment_db,
        )

        db_env = os.getenv("LLMC_ENRICH_DB")
        db_path: Path | None
        if not db_env or not Path(db_env).exists():
            db_path = discover_enrichment_db(Path(repo_root), getattr(res, "items", None))
        else:
            db_path = Path(db_env)
        if not db_path or not db_path.exists():
            return res

        stats = EnrichStats()
        store = SqliteEnrichmentStore(db_path)
        max_chars = _enrichment_max_chars()
        res = attach_enrichments_to_where_used(
            res, store, max_snippets=1, max_chars=max_chars, stats=stats
        )

        if str(os.getenv("LLMC_ENRICH_LOG", "")).lower() in {"1", "true", "yes"}:
            _enrich_log.info(
                "enrich attach (where-used): db=%s items=%d attached=%d line=%d path=%d truncated=%d",
                db_path,
                len(getattr(res, "items", []) or []),
                stats.snippets_attached,
                stats.line_matches,
                stats.path_matches,
                stats.fields_truncated,
            )
    except Exception:
        return res
    return res


def _maybe_attach_enrichment_lineage(repo_root: str, res: LineageResult) -> LineageResult:
    if not _enrichment_enabled():
        return res
    try:
        from tools.rag_nav.enrichment import (
            EnrichStats,
            SqliteEnrichmentStore,
            attach_enrichments_to_lineage,
            discover_enrichment_db,
        )

        db_env = os.getenv("LLMC_ENRICH_DB")
        db_path: Path | None
        items = getattr(res, "items", None)
        if not db_env or not Path(db_env).exists():
            db_path = discover_enrichment_db(Path(repo_root), items)
        else:
            db_path = Path(db_env)
        if not db_path or not db_path.exists() or items is None:
            return res

        stats = EnrichStats()
        store = SqliteEnrichmentStore(db_path)
        max_chars = _enrichment_max_chars()
        res = attach_enrichments_to_lineage(
            res, store, max_snippets=1, max_chars=max_chars, stats=stats
        )

        if str(os.getenv("LLMC_ENRICH_LOG", "")).lower() in {"1", "true", "yes"}:
            _enrich_log.info(
                "enrich attach (lineage): db=%s items=%d attached=%d line=%d path=%d truncated=%d",
                db_path,
                len(items or []),
                stats.snippets_attached,
                stats.line_matches,
                stats.path_matches,
                stats.fields_truncated,
            )
    except Exception:
        return res
    return res
