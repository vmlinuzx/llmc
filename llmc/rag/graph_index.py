"""
Lightweight graph indices for where-used and lineage queries backed by
`.llmc/rag_graph.json`.

The index is intentionally tolerant of different graph shapes:
- Nav graph payloads with `nodes`/`edges` or `vertices`/`links`
- Schema graphs with `entities`/`relations`
- Artifacts wrapped in a `schema_graph` field

Public API:
- load_indices(repo_root) -> GraphIndices
- where_used_files(indices, symbol, limit) -> list[str]
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
import json
from pathlib import Path
import time
from typing import Any

ALLOWED_EDGE_TYPES: set[str] = {"CALLS", "IMPORTS", "EXTENDS", "READS", "WRITES"}

# Cache for loaded graph indices: repo_path -> (mtime, GraphIndices)
# This avoids re-parsing large JSON graphs on every tool call
_INDICES_CACHE: dict[str, tuple[float, GraphIndices]] = {}



class GraphNotFound(FileNotFoundError):
    """Raised when a usable graph artifact cannot be loaded."""


@dataclass
class Node:
    """Minimal node representation for indexing where-used relationships."""

    nid: str
    path: str = ""
    name: str = ""  # symbol-like string (fully-qualified if available)


@dataclass
class GraphIndices:
    """In-memory indices derived from the graph artifact."""

    # Map a "symbol key" to the set of file paths that reference/use it (where-used).
    symbol_to_files: dict[str, set[str]] = field(default_factory=dict)
    # Lineage: for a given source symbol key, files of its callees (downstream).
    symbol_to_callee_files: dict[str, set[str]] = field(default_factory=dict)


def _read_graph_payload(path: Path) -> dict:
    """
    Read and normalize the raw graph JSON payload.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise GraphNotFound(str(path))
        data: dict[str, Any] = raw
    except Exception as e:
        raise GraphNotFound(f"Bad JSON in {path}: {e}")

    if not isinstance(data, dict):
        raise GraphNotFound(str(path))

    # Some artifacts may wrap the schema graph in a `schema_graph` field.
    if isinstance(data.get("schema_graph"), dict):
        return dict(data["schema_graph"])

    return data


def _norm_path(path_str: str) -> str:
    """Normalize a path-like string to a POSIX-style relative path when possible."""
    if not path_str:
        return ""
    # Strip line-range suffixes like "foo.py:10-20" if present.
    base = path_str.split(":", 1)[0]
    return str(Path(base).as_posix())


def _candidate_keys(name: str) -> list[str]:
    """
    Generate multiple keys for matching a symbol string robustly.

    Examples:
      - "tools.auth.jwt:verify_jwt"
        -> ["tools.auth.jwt:verify_jwt", "verify_jwt", "jwt.verify_jwt", "verify_jwt"]
      - "pkg.mod.func" -> ["pkg.mod.func", "func"]
    """
    out: list[str] = []
    if not name:
        return out

    value = str(name)
    out.append(value)

    # Split on "module:member" then on "." to capture the tail.
    tail = value.split(":", 1)[-1]
    out.append(tail)

    if "." in tail and ":" in value:
        module_part = value.split(":", 1)[0].split(".")[-1]
        tail_leaf = tail.split(".")[-1]
        out.append(f"{module_part}.{tail_leaf}")

    if "." in value:
        out.append(value.split(".")[-1])

    # Deduplicate while preserving order.
    seen: set[str] = set()
    uniq: list[str] = []
    for key in out:
        if key and key not in seen:
            seen.add(key)
            uniq.append(key)
    return uniq


def _index_nodes(graph: dict) -> dict[str, Node]:
    """
    Build a mapping from node id to Node, tolerating multiple shapes.

    Supports:
    - Nav graphs: graph["nodes"] or graph["vertices"]
    - Schema graphs: graph["entities"]
    """
    nodes = graph.get("nodes") or graph.get("vertices") or graph.get("entities") or []
    id_to_node: dict[str, Node] = {}

    if not isinstance(nodes, list):
        return id_to_node

    for raw in nodes:
        if not isinstance(raw, dict):
            continue

        nid = str(raw.get("id") or raw.get("nid") or raw.get("name") or "")

        # Prefer explicit file-relative paths; fall back to generic path fields.
        path = _norm_path(
            raw.get("file_path")
            or raw.get("path")
            or raw.get("file")
            or raw.get("filepath")
            or ""
        )

        # Prefer explicit symbol/name fields including metadata.symbol when available.
        metadata = raw.get("metadata") or {}
        name = str(
            raw.get("symbol")
            or metadata.get("symbol")
            or raw.get("name")
            or raw.get("label")
            or ""
        )

        if not nid and name:
            nid = name

        if not nid:
            continue

        id_to_node[nid] = Node(nid=nid, path=path, name=name)

    return id_to_node


def _iter_edges(graph: dict) -> Iterable[dict]:
    """
    Yield edge-like dicts from the graph, normalizing different layouts.

    Prefers:
    - graph["edges"] or graph["links"]
    - Otherwise projects graph["relations"] into edge dicts.
    """
    edges = graph.get("edges") or graph.get("links")
    if isinstance(edges, list) and edges:
        for edge in edges:
            if isinstance(edge, dict):
                yield edge
        return

    relations = graph.get("relations") or []
    if not isinstance(relations, list):
        return

    for rel in relations:
        if not isinstance(rel, dict):
            continue
        yield {
            "type": rel.get("edge") or rel.get("type") or "",
            "source": rel.get("src") or rel.get("from"),
            "target": rel.get("dst") or rel.get("to"),
        }


def _accumulate(mapping: dict[str, set[str]], key: str, path: str) -> None:
    """Accumulate a file path under the given symbol key."""
    if not key or not path:
        return
    mapping.setdefault(key, set()).add(path)


def build_indices_from_graph(graph: dict) -> GraphIndices:
    """
    Construct GraphIndices from a tolerant graph dict representation.

    Edge semantics:
    - For allowed edge types, treat `src uses dst` and record the source file
      under keys derived from the destination symbol.
    """
    id_to_node = _index_nodes(graph)
    symbol_to_files: dict[str, set[str]] = {}
    symbol_to_callee_files: dict[str, set[str]] = {}

    for edge in _iter_edges(graph):
        etype = str(edge.get("type") or edge.get("label") or "").upper()
        if etype not in ALLOWED_EDGE_TYPES:
            continue

        src = edge.get("src") or edge.get("source")
        dst = edge.get("dst") or edge.get("target")

        src_node = id_to_node.get(str(src)) if src is not None else None
        dst_node = id_to_node.get(str(dst)) if dst is not None else None

        # Fallback: edges may carry file/symbol identifiers directly.
        if src_node is None and isinstance(src, str):
            src_node = Node(nid=str(src), path=_norm_path(src), name=str(src))
        if dst_node is None and isinstance(dst, str):
            dst_node = Node(nid=str(dst), path=_norm_path(dst), name=str(dst))

        if not src_node or not dst_node:
            continue

        symbol_name = dst_node.name or dst_node.nid
        if symbol_name:
            for key in _candidate_keys(symbol_name):
                # where-used semantics: source file is the user of the destination symbol.
                _accumulate(symbol_to_files, key, src_node.path or dst_node.path)

        # Lineage downstream: for a given SRC symbol, record callee files.
        if etype == "CALLS":
            src_symbol = src_node.name or src_node.nid
            if src_symbol:
                for key in _candidate_keys(src_symbol):
                    _accumulate(
                        symbol_to_callee_files, key, dst_node.path or src_node.path
                    )

    return GraphIndices(
        symbol_to_files=symbol_to_files,
        symbol_to_callee_files=symbol_to_callee_files,
    )


def load_indices(repo_root: Path | str) -> GraphIndices:
    """
    Load GraphIndices for the given repository root.

    Uses mtime-aware caching to avoid re-parsing the JSON graph on every call.
    Cache invalidates when the underlying file changes.

    Raises GraphNotFound when the `.llmc/rag_graph.json` payload is missing
    or cannot be interpreted as a usable graph.
    """
    root_path = Path(repo_root)
    graph_path = root_path / ".llmc" / "rag_graph.json"
    if not graph_path.is_file():
        raise GraphNotFound(str(graph_path))

    # Check cache with mtime validation
    cache_key = str(graph_path.resolve())
    now = time.time()
    
    try:
        current_mtime = graph_path.stat().st_mtime
    except OSError:
        current_mtime = 0.0
    
    cached = _INDICES_CACHE.get(cache_key)
    if cached is not None:
        cached_mtime, cached_indices = cached
        # Revalidate: if mtime matches and we're within TTL, use cached
        if current_mtime == cached_mtime:
            return cached_indices

    # Cache miss or stale - reload
    graph_payload = _read_graph_payload(graph_path)
    indices = build_indices_from_graph(graph_payload)

    # If we ended up with no indices at all, treat this as effectively missing.
    if not indices.symbol_to_files and not indices.symbol_to_callee_files:
        raise GraphNotFound(str(graph_path))

    # Store in cache
    _INDICES_CACHE[cache_key] = (current_mtime, indices)
    
    return indices


def where_used_files(indices: GraphIndices, symbol: str, limit: int = 50) -> list[str]:
    """
    Return file paths that reference `symbol`, using strict and suffix matches.

    The result list is de-duplicated and capped at `limit` entries.
    """
    if not symbol or not indices.symbol_to_files:
        return []

    limit = max(1, int(limit)) if limit > 0 else 1
    keys = _candidate_keys(symbol)

    seen: set[str] = set()
    out: list[str] = []

    # Exact key matches first.
    for key in keys:
        for path in indices.symbol_to_files.get(key, ()):
            if path and path not in seen:
                seen.add(path)
                out.append(path)
                if len(out) >= limit:
                    return out

    # Suffix/looser matches for any remaining capacity.
    if len(out) < limit:
        target_suffix = symbol.lower()
        for key, paths in indices.symbol_to_files.items():
            if key.lower().endswith(target_suffix):
                for path in paths:
                    if path and path not in seen:
                        seen.add(path)
                        out.append(path)
                        if len(out) >= limit:
                            return out

    return out[:limit]


def lineage_files(
    indices: GraphIndices, symbol: str, direction: str, limit: int = 50
) -> list[str]:
    """
    Return files related by CALLS edges for lineage queries.

    Semantics:
    - direction == "upstream": callers of symbol (same as where-used).
    - direction == "downstream": callees of symbol.
    """
    if not symbol:
        return []

    direction_norm = (direction or "downstream").lower()
    if direction_norm == "upstream":
        return where_used_files(indices, symbol, limit=limit)

    # Downstream: use symbol_to_callee_files index.
    keys = _candidate_keys(symbol)
    limit = max(1, int(limit)) if limit > 0 else 1
    seen: set[str] = set()
    out: list[str] = []

    for key in keys:
        for path in indices.symbol_to_callee_files.get(key, ()):
            if path and path not in seen:
                seen.add(path)
                out.append(path)
                if len(out) >= limit:
                    return out

    if len(out) < limit:
        sym_lower = symbol.lower()
        for key, paths in indices.symbol_to_callee_files.items():
            if key.lower().endswith(sym_lower):
                for path in paths:
                    if path and path not in seen:
                        seen.add(path)
                        out.append(path)
                        if len(out) >= limit:
                            return out

    return out[:limit]
