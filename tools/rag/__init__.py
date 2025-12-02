# RAG tools module - placeholder for missing functions
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Optional


def load_status(repo_root: Path) -> object | None:
    """Load index status for a repository"""
    status_file = status_path(repo_root)
    if status_file.exists():
        data = json.loads(status_file.read_text())
        from tools.rag_nav.models import IndexStatus

        return IndexStatus(
            repo=str(data.get("repo", str(repo_root))),
            index_state=data.get("index_state", "fresh"),
            last_indexed_at=data.get("last_indexed_at", ""),
            last_indexed_commit=data.get("last_indexed_commit"),
            schema_version=str(data.get("schema_version", "1")),
            last_error=data.get("last_error"),
        )
    return None


def save_status(repo_root: Path, status: object) -> None:
    """Save index status for a repository"""
    status_file = status_path(repo_root)
    status_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "repo": getattr(status, "repo", str(repo_root)),
        "index_state": getattr(status, "index_state", "fresh"),
        "last_indexed_at": getattr(status, "last_indexed_at", datetime.now().isoformat()),
        "last_indexed_commit": getattr(status, "last_indexed_commit", None),
        "schema_version": getattr(status, "schema_version", "1"),
        "last_error": getattr(status, "last_error", None),
    }
    status_file.write_text(json.dumps(payload))


def status_path(repo_root: Path) -> Path:
    """Get path to status file for a repository"""
    return repo_root / ".llmc" / "rag" / "index_status.json"


def compute_route(repo_root: Path) -> object:
    """Compute routing decision for a repository"""

    class Route:
        use_rag = True
        freshness_state = "FRESH"

    return Route()


def build_graph_for_repo(repo_root: Path) -> object:
    """Build schema graph for a repository"""

    class Status:
        index_state = "fresh"
        schema_version = "2"

    status = Status()
    save_status(repo_root, status)

    # Scan for Python files
    files = []
    entities = []
    relations = []

    for root, dirs, filenames in os.walk(repo_root):
        # Skip hidden directories and __pycache__
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for filename in filenames:
            if filename.endswith(".py"):
                file_path = Path(root) / filename
                relative_path = file_path.relative_to(repo_root)
                files.append(str(relative_path))

                # Create entity for this file
                entities.append(
                    {
                        "id": str(relative_path).replace("/", ".").replace(".py", ""),
                        "name": filename,
                        "type": "file",
                        "path": str(relative_path),
                    }
                )

    # Look for inheritance relationships
    for file_path_str in files:
        if file_path_str.endswith(".py"):
            full_path = repo_root / file_path_str
            try:
                content = full_path.read_text()
                # Look for class inheritance patterns
                for line in content.split("\n"):
                    line = line.strip()
                    if line.startswith("class ") and "(" in line:
                        # Extract base class
                        parts = line.split("(", 1)
                        if len(parts) > 1:
                            base_part = parts[1].split(")")[0].strip()
                            if base_part and not base_part.startswith("_"):
                                # Add relation
                                relations.append(
                                    {
                                        "from": file_path_str.replace("/", ".").replace(".py", ""),
                                        "to": base_part,
                                        "edge": "extends",
                                    }
                                )
            except Exception:
                pass  # Skip files that can't be read

    # Create graph data
    graph_path = _graph_path(repo_root)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_data = {
        "repo": str(repo_root.resolve()),
        "schema_version": "2",
        "files": files,
        "schema_graph": {"entities": entities, "relations": relations},
    }
    graph_path.write_text(json.dumps(graph_data))

    return status


def _graph_path(repo_root: Path) -> Path:
    """Get path to graph file for a repository"""
    return repo_root / ".llmc" / "rag" / "schema_graph.json"


def tool_rag_search(
    query: str,
    repo_root: Path,
    limit: int = 10,
):
    """
    Thin adapter to tools.rag_nav.tool_handlers.tool_rag_search.

    This keeps the public tools.rag API stable while delegating the
    actual implementation to the rag_nav module.
    """
    from tools.rag_nav.tool_handlers import tool_rag_search as _impl

    return _impl(query=query, repo_root=repo_root, limit=limit)


def tool_rag_where_used(
    symbol: str,
    repo_root: Path,
    limit: int = 10,
):
    """
    Thin adapter to tools.rag_nav.tool_handlers.tool_rag_where_used.
    """
    from tools.rag_nav.tool_handlers import tool_rag_where_used as _impl

    return _impl(symbol=symbol, repo_root=repo_root, limit=limit)


def tool_rag_lineage(
    symbol: str,
    direction: str,
    repo_root: Path,
    max_results: int = 50,
):
    """
    Thin adapter to tools.rag_nav.tool_handlers.tool_rag_lineage.
    """
    from tools.rag_nav.tool_handlers import tool_rag_lineage as _impl

    return _impl(symbol=symbol, direction=direction, repo_root=repo_root, max_results=max_results)
