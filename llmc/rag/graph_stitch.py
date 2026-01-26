from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class Neighbor:
    """Neighbor file in the schema graph, used to stitch context."""

    path: str
    weight: float = 1.0
    reason: str = "edge"


class GraphNotFound(FileNotFoundError):
    """Raised when .llmc/rag_graph.json is missing."""


def _read_json(p: Path) -> dict:
    return dict(json.loads(p.read_text(encoding="utf-8")))


def _normalize_path(p: str) -> str:
    return str(Path(p).as_posix())


def _index_edges(graph: dict) -> dict[str, set[str]]:
    """Heuristic neighbor index from a generic node/edge JSON graph."""
    nodes = graph.get("nodes") or graph.get("vertices") or []
    id_to_path: dict[str, str] = {}
    for n in nodes:
        nid = str(n.get("id") or n.get("nid") or n.get("name") or "")
        p = n.get("path") or n.get("file") or n.get("filepath") or ""
        if nid and p:
            id_to_path[nid] = _normalize_path(p)

    neighbors: dict[str, set[str]] = {}
    edges = graph.get("edges") or graph.get("links") or []
    for e in edges:
        et = (e.get("type") or e.get("label") or "").upper()
        if et not in {"CALLS", "IMPORTS", "EXTENDS", "READS", "WRITES"}:
            continue
        src = e.get("src") or e.get("source")
        dst = e.get("dst") or e.get("target")

        src_path = id_to_path.get(str(src), None) if src is not None else None
        dst_path = id_to_path.get(str(dst), None) if dst is not None else None

        if (
            src_path is None
            and isinstance(src, str)
            and ("/" in src or src.endswith(".py"))
        ):
            src_path = _normalize_path(src)
        if (
            dst_path is None
            and isinstance(dst, str)
            and ("/" in dst or dst.endswith(".py"))
        ):
            dst_path = _normalize_path(dst)

        if not src_path or not dst_path or src_path == dst_path:
            continue

        neighbors.setdefault(src_path, set()).add(dst_path)
        neighbors.setdefault(dst_path, set()).add(src_path)

    return neighbors


def load_neighbor_index(repo_root: Path) -> dict[str, set[str]] | None:
    """Load neighbor index, preferring SQLite when available.
    
    Returns None if SQLite is available (stitch_neighbors will use DB directly).
    Returns dict if using JSON fallback.
    """
    db_path = repo_root / ".llmc" / "rag_graph.db"
    if db_path.is_file():
        # Signal to caller to use SQLite directly
        return None
    
    # JSON fallback
    graph_path = repo_root / ".llmc" / "rag_graph.json"
    if not graph_path.exists():
        raise GraphNotFound(str(graph_path))
    graph = _read_json(graph_path)
    return _index_edges(graph)


def stitch_neighbors(
    repo_root: Path, seed_paths: Iterable[str], limit: int, hops: int = 1
) -> list[Neighbor]:
    """Return neighbor file paths (1..hops) for given seed paths, unique and capped.
    
    Uses O(1) SQLite queries when database is available.
    Falls back to in-memory JSON index otherwise.
    """
    idx = load_neighbor_index(repo_root)
    seed_list = list(seed_paths)
    
    # SQLite path: O(1) query via GraphDatabase
    if idx is None:
        try:
            from llmc.rag.graph_db import GraphDatabase
            
            db_path = repo_root / ".llmc" / "rag_graph.db"
            with GraphDatabase(db_path) as db:
                neighbor_paths = db.get_file_neighbors(seed_list, limit=limit)
            return [Neighbor(path=p, weight=1.0, reason="neighbor") for p in neighbor_paths]
        except Exception:
            # Fallback to JSON if SQLite fails
            graph_path = repo_root / ".llmc" / "rag_graph.json"
            if not graph_path.exists():
                raise GraphNotFound(str(graph_path)) from None
            idx = _index_edges(_read_json(graph_path))
    
    # In-memory path: dict traversal (JSON-based)
    seen: set[str] = set(seed_list)
    frontier: set[str] = set(seed_list)
    out: list[Neighbor] = []

    for _ in range(max(1, hops)):
        next_frontier: set[str] = set()
        for p in list(frontier):
            for n in idx.get(p, ()):
                if n in seen:
                    continue
                seen.add(n)
                next_frontier.add(n)
                out.append(Neighbor(path=n, weight=1.0, reason="neighbor"))
                if len(out) >= limit:
                    return out
        frontier = next_frontier
        if not frontier:
            break
    return out


def expand_search_items(
    repo_root: Path, items: list, max_expansion: int = 20, hops: int = 1
):
    """Expand search results with neighbor files from the graph.

    - If the graph is missing/unreadable, returns the original items.
    - Returns either just items (unchanged) or a tuple (items, neighbors).
    """
    try:
        raw_seed = [getattr(it, "file", None) for it in items]
        seed: list[str] = [str(s) for s in raw_seed if s]
        neighbors = stitch_neighbors(
            repo_root, seed_paths=seed, limit=max_expansion, hops=hops
        )
    except Exception:
        return items

    return items, neighbors
