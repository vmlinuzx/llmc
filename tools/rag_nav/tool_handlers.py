from __future__ import annotations

"""
Phase 3 — Patch P3: Minimal graph-backed results for RAG Nav tools.

Reads `.llmc/rag_graph.json` under the provided repo_root and returns real items
for search/where-used/lineage using lightweight heuristics. No DB writes, no
advanced scoring — just enough to satisfy tests with deterministic behavior.
"""

import json
import os
from pathlib import Path
from typing import Optional, Iterable, Dict, Any, List, Set, Tuple
import logging

from tools.rag_nav.models import (
    Snippet,
    SnippetLocation,
    SearchItem,
    SearchResult,
    WhereUsedItem,
    WhereUsedResult,
    LineageItem,
    LineageResult,
)

_enrich_log = logging.getLogger("llmc.enrich")


_GRAPH_REL_PATH = os.path.join(".llmc", "rag_graph.json")
_SUPPORTED_EDGE_TYPES = {"CALLS", "IMPORTS", "READS", "WRITES", "USES"}


def _rag_graph_path(repo_root: Path | str) -> Path:
    """Internal helper: path to the RAG Nav graph JSON."""
    return Path(repo_root) / ".llmc" / "rag_graph.json"


def _graph_path(repo_root: Path | str) -> Path:
    """
    Compatibility wrapper for the legacy schema graph path.

    Tests for the Phase 2 builder expect this function to return the
    path used by tools.rag.build_graph_for_repo (schema_graph.json).
    """
    from tools.rag import _graph_path as _core_graph_path

    return _core_graph_path(Path(repo_root))


def _load_graph(repo_root: str) -> tuple[list[dict], list[dict]]:
    """Return (nodes, edges). If missing or invalid, return ([], [])."""
    path = _rag_graph_path(repo_root)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        nodes = data.get("nodes") or data.get("entities") or []
        edges = data.get("edges") or []
        # Allow consuming schema_graph artifacts by projecting relations into edges.
        if not edges and isinstance(data.get("schema_graph"), dict):
            rels = data["schema_graph"].get("relations") or []
            if isinstance(rels, list):
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


def _node_span(n: dict) -> tuple[Optional[int], Optional[int]]:
    span = n.get("span") or n.get("loc") or {}
    start = span.get("start_line") or span.get("start") or span.get("line_start") or n.get("start_line")
    end = span.get("end_line") or span.get("end") or span.get("line_end") or n.get("end_line")
    try:
        start_i = int(start) if start is not None else None
        end_i = int(end) if end is not None else None
        return start_i, end_i
    except Exception:
        return None, None


def _read_snippet(repo_root: str, path: str, start_line: Optional[int], end_line: Optional[int]) -> Snippet:
    """Read file and slice [start_line, end_line]. Lines are 1-based, inclusive."""
    abspath = os.path.join(repo_root, path) if path else ""
    text = ""
    sl = start_line or 1
    el = end_line or (sl + 15)
    if os.path.isfile(abspath):
        try:
            with open(abspath, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            total = len(lines)
            sl = max(1, min(sl, total if total else 1))
            el = max(sl, min(el, total if total else sl))
            text = "".join(lines[sl - 1 : el])
        except Exception:
            text = ""
    return Snippet(text=text, location=SnippetLocation(path=path or "", start_line=sl, end_line=el))


def _max_n(max_results: Optional[int], default: int = 20) -> int:
    try:
        if max_results is None:
            return default
        return max(1, int(max_results))
    except Exception:
        return default


def _index_nodes(nodes: list[dict]) -> tuple[Dict[str, dict], Dict[str, List[dict]]]:
    by_id: Dict[str, dict] = {}
    by_name_lower: Dict[str, List[dict]] = {}
    for n in nodes:
        nid = str(n.get("id") or _node_name(n))
        by_id[nid] = n
        nm = _node_name(n).lower()
        if nm:
            by_name_lower.setdefault(nm, []).append(n)
    return by_id, by_name_lower


def _match_nodes(nodes: list[dict], query: str) -> List[dict]:
    q = (query or "").lower().strip()
    if not q:
        return []
    out: List[dict] = []
    seen: Set[int] = set()
    for i, n in enumerate(nodes):
        name = _node_name(n).lower()
        path = _node_path(n).lower()
        if q in name or q in path:
            if i not in seen:
                seen.add(i)
                out.append(n)
    return out


def _resolve_symbol_nodes(nodes: list[dict], symbol: str) -> List[dict]:
    if not symbol:
        return []
    q = symbol.lower()
    out: List[dict] = []
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
    from tools.rag import build_graph_for_repo as _core_build_graph_for_repo, _graph_path as _core_graph_path
    from tools.rag.schema import build_graph_for_repo as _schema_build_graph_for_repo

    repo_root_path = Path(repo_root)

    # First, build the legacy graph + status so existing callers and tests
    # that inspect schema_graph.json continue to work.
    status = _core_build_graph_for_repo(repo_root_path)

    # Next, build an AST-only schema graph (no DB required) and derive a
    # minimal nodes/edges representation for RAG Nav.
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

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
            span: Dict[str, int] = {}
            if entity.start_line is not None:
                span["start_line"] = int(entity.start_line)
            if entity.end_line is not None:
                span["end_line"] = int(entity.end_line)

            node: Dict[str, Any] = {
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
                if any(part in {".git", ".venv", "venv", "__pycache__", "node_modules"} for part in path.parts):
                    continue
                yield path

        # First pass: collect defined symbol names by scanning for def/class.
        defined_symbols: Set[str] = set()
        file_paths: List[Path] = []
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


# --- Fallback helpers (local scan) ---------------------------------------------
def _iter_repo_py_files(repo_root):
    import os
    skip_dirs = {".git", ".llmc", ".trash", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache"}
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
                with open(abspath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                for i, line in enumerate(lines, start=1):
                    if needle in line:
                        sl = max(1, i - 2)
                        el = min(len(lines), i + 2)
                        text = "".join(lines[sl-1:el])
                        items.append((rel, sl, el, text))
                        if len(items) >= max_items:
                            return items
            except Exception:
                continue
    except Exception:
        pass
    return items


# --- Context Gateway integration ----------------------------------------------
from pathlib import Path as _Path

from tools.rag.config import load_rerank_weights
from tools.rag.graph_index import (
    GraphNotFound as IndexGraphNotFound,
    lineage_files as lineage_files_from_index,
    load_indices as load_graph_indices,
    where_used_files as where_used_files_from_index,
)
from tools.rag_nav.gateway import compute_route as _compute_route
from tools.rag.db_fts import fts_search, RagDbNotFound, FtsHit
from tools.rag.rerank import rerank_hits, RerankHit
from tools.rag.graph_stitch import expand_search_items, Neighbor, GraphNotFound


def _neighbors_to_items(neigh: List[Neighbor]) -> List[SearchItem]:
    items: List[SearchItem] = []
    for n in neigh:
        loc = SnippetLocation(path=n.path, start_line=1, end_line=1)
        items.append(SearchItem(file=n.path, snippet=Snippet(text="", location=loc)))
    return items


def tool_rag_search(repo_root, query: str, limit: Optional[int] = None) -> SearchResult:
    """Search using DB FTS + reranker + 1-hop graph stitch when route allows RAG."""
    route = _compute_route(_Path(repo_root))
    repo_root_path = _Path(repo_root)
    max_results = _max_n(limit, default=20)
    source = "RAG_GRAPH" if route.use_rag else "LOCAL_FALLBACK"

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
            items: List[SearchItem] = [
                SearchItem(
                    file=h.file,
                    snippet=Snippet(
                        text=h.text,
                        location=SnippetLocation(path=h.file, start_line=h.start_line, end_line=h.end_line),
                    ),
                )
                for h in ranked
            ]
            truncated = len(hits) > len(items)

            # P9c: graph-stitch 1-hop neighbors to fill remaining budget.
            remaining = max(0, max_results - len(items))
            if remaining > 0:
                try:
                    res = expand_search_items(repo_root_path, items, max_expansion=min(remaining, max_results), hops=1)
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
            return _maybe_attach_enrichment_search(repo_root, res)
        except (RagDbNotFound, RuntimeError):
            source = "LOCAL_FALLBACK"

    # Fallback: local grep over .py files when no RAG route or DB issues.
    grep_hits = _grep_snippets(repo_root, query, max_results)
    items: List[SearchItem] = []
    for rel, sl, el, text in grep_hits:
        items.append(
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
        items=items,
        truncated=False,
        source=source,
        freshness_state=getattr(route, "freshness_state", "UNKNOWN"),
    )
    return _maybe_attach_enrichment_search(repo_root, res)


def tool_rag_where_used(repo_root, symbol: str, limit: Optional[int] = None) -> WhereUsedResult:
    """Where-used query using graph indices when the Context Gateway allows RAG."""
    route = _compute_route(_Path(repo_root))
    max_results = _max_n(limit, default=50)
    source = "RAG_GRAPH" if getattr(route, "use_rag", False) else "LOCAL_FALLBACK"

    if getattr(route, "use_rag", False):
        try:
            indices = load_graph_indices(_Path(repo_root))
            files = where_used_files_from_index(indices, symbol, limit=max_results)
            items: List[WhereUsedItem] = []
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
    return _maybe_attach_enrichment_where_used(repo_root, res)


def tool_rag_lineage(
    repo_root,
    symbol: str,
    direction: str,
    max_results: Optional[int] = None,
) -> LineageResult:
    """Lineage query using graph indices when the Context Gateway allows RAG."""
    route = _compute_route(_Path(repo_root))
    limit = _max_n(max_results, default=50)
    dir_norm = (direction or "downstream").lower().strip()
    normalized_direction = "upstream" if dir_norm in ("upstream", "callers") else "downstream"
    source = "RAG_GRAPH" if getattr(route, "use_rag", False) else "LOCAL_FALLBACK"

    if getattr(route, "use_rag", False):
        try:
            indices = load_graph_indices(_Path(repo_root))
            files = lineage_files_from_index(
                indices,
                symbol,
                direction=normalized_direction,
                limit=limit,
            )
            items: List[LineageItem] = []
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
            return _maybe_attach_enrichment_lineage(repo_root, res)
        except (IndexGraphNotFound, Exception):
            # Any graph loading/indexing issue should route to the local fallback.
            source = "LOCAL_FALLBACK"

    # Fallback: naive grep for callsites "symbol(" as pseudo-lineage.
    grep_hits = _grep_snippets(repo_root, f"{symbol}(", limit)
    items: List[LineageItem] = []
    for rel, sl, el, text in grep_hits:
        items.append(
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
        items=items,
        truncated=False,
        source=source,
        freshness_state=route.freshness_state,
    )
    return _maybe_attach_enrichment_lineage(repo_root, res)


def _enrichment_enabled() -> bool:
    flag = str(os.getenv("LLMC_ENRICH", "")).lower()
    attach = str(os.getenv("LLMC_ENRICH_ATTACH", "")).lower()
    return flag in {"1", "true", "yes", "on"} or attach in {"1", "true", "yes"}


def _enrichment_max_chars() -> Optional[int]:
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
        db_path: Optional[Path]
        if not db_env or not Path(db_env).exists():
            db_path = discover_enrichment_db(Path(repo_root), getattr(res, "items", None))
        else:
            db_path = Path(db_env)
        if not db_path or not db_path.exists():
            return res

        stats = EnrichStats()
        store = SqliteEnrichmentStore(db_path)
        max_chars = _enrichment_max_chars()
        res = attach_enrichments_to_search_result(res, store, max_snippets=1, max_chars=max_chars, stats=stats)

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
        db_path: Optional[Path]
        if not db_env or not Path(db_env).exists():
            db_path = discover_enrichment_db(Path(repo_root), getattr(res, "items", None))
        else:
            db_path = Path(db_env)
        if not db_path or not db_path.exists():
            return res

        stats = EnrichStats()
        store = SqliteEnrichmentStore(db_path)
        max_chars = _enrichment_max_chars()
        res = attach_enrichments_to_where_used(res, store, max_snippets=1, max_chars=max_chars, stats=stats)

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
        db_path: Optional[Path]
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
        res = attach_enrichments_to_lineage(res, store, max_snippets=1, max_chars=max_chars, stats=stats)

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
