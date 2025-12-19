from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from llmc.rag.schema import SchemaGraph


def load_graph(repo_root: Path) -> SchemaGraph | None:
    """Loads the schema graph for the repository.

    Args:
        repo_root: The root path of the repository.

    Returns:
        The loaded schema graph, or None if the graph is not found.
    """
    graph_path = repo_root / ".llmc" / "rag_graph.json"
    if not graph_path.exists():
        return None
    try:
        return SchemaGraph.load(graph_path)
    except Exception:
        return None


def get_file_context(graph: SchemaGraph | None, file_path: str) -> Dict[str, Any]:
    """Get graph context for a file.

    Args:
        graph: The schema graph.
        file_path: The path to the file.

    Returns:
        A dictionary containing the graph context for the file.
    """
    ctx: Dict[str, Any] = {
        "purpose": None,
        "called_by": [],
        "imports": [],
        "exports": [],
        "related": [],
    }
    if not graph:
        return ctx

    file_entity = None
    for entity in graph.entities:
        if entity.file_path == file_path:
            file_entity = entity
            break

    if not file_entity:
        return ctx

    ctx["purpose"] = file_entity.metadata.get("summary")

    for edge in graph.relations:
        if edge.edge == "calls":
            dst_entity = next(
                (e for e in graph.entities if e.id == edge.dst), None
            )
            if dst_entity and dst_entity.file_path == file_path:
                src_entity = next(
                    (e for e in graph.entities if e.id == edge.src), None
                )
                if src_entity:
                    ctx["called_by"].append(
                        {
                            "file": src_entity.file_path,
                            "symbol": src_entity.id,
                            "line": src_entity.start_line,
                        }
                    )

        if edge.edge == "imports":
            src_entity = next(
                (e for e in graph.entities if e.id == edge.src), None
            )
            if src_entity and src_entity.file_path == file_path:
                ctx["imports"].append(edge.dst)

    for entity in graph.entities:
        if entity.file_path == file_path and entity.kind in (
            "function",
            "class",
        ):
            ctx["exports"].append(entity.id)

    related_files = set()
    for edge in graph.relations:
        src_entity = next(
            (e for e in graph.entities if e.id == edge.src), None
        )
        dst_entity = next(
            (e for e in graph.entities if e.id == edge.dst), None
        )
        if (
            src_entity
            and dst_entity
            and src_entity.file_path == file_path
            and dst_entity.file_path
        ):
            related_files.add(dst_entity.file_path)
        if (
            src_entity
            and dst_entity
            and dst_entity.file_path == file_path
            and src_entity.file_path
        ):
            related_files.add(src_entity.file_path)

    # Remove the file itself from the related files
    related_files.discard(file_path)

    ctx["related"] = sorted(list(related_files))[:5]

    return ctx


def get_symbol_context(graph: SchemaGraph | None, symbol: str) -> Dict[str, Any]:
    """Get graph context for a symbol.

    Args:
        graph: The schema graph.
        symbol: The symbol to get the context for.

    Returns:
        A dictionary containing the graph context for the symbol.
    """
    ctx: Dict[str, Any] = {
        "callers": [],
        "callees": [],
        "extends": None,
    }
    if not graph:
        return ctx

    for edge in graph.relations:
        if edge.edge == "calls":
            if edge.dst == symbol:
                ctx["callers"].append(edge.src)
            if edge.src == symbol:
                ctx["callees"].append(edge.dst)
        elif edge.edge == "extends":
            if edge.src == symbol:
                ctx["extends"] = edge.dst

    return ctx
