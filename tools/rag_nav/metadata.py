"""Metadata helpers for RAG Nav (path + JSON I/O).

Implements:
- status_path(repo_root) -> Path
- save_status(repo_root, status) -> Path
- load_status(repo_root) -> IndexStatus | None
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Union
import json

from tools.rag_nav.models import IndexStatus


def status_path(repo_root: Path) -> Path:
    """Return the canonical path for the index status JSON in a repo."""
    repo_root = Path(repo_root).expanduser().resolve()
    return repo_root / ".llmc" / "rag" / "index_status.json"


def save_status(repo_root: Path, status: Union[IndexStatus, Dict[str, Any]]) -> Path:
    """Serialize and write index status to disk, ensuring parent dirs exist."""
    path = status_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(status, IndexStatus):
        data = status.to_dict()
    else:
        data = dict(status)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_status(repo_root: Path) -> Optional[IndexStatus]:
    """Load index status; return None if file missing or JSON invalid."""
    path = status_path(repo_root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Coerce dict → IndexStatus, tolerate missing keys
        return IndexStatus(
            repo=str(data.get("repo") or str(repo_root)),
            index_state=data.get("index_state") or "error",
            last_indexed_at=data.get("last_indexed_at"),
            last_indexed_commit=data.get("last_indexed_commit"),
            schema_version=str(data.get("schema_version", "1")),
            last_error=data.get("last_error"),
        )
    except Exception:
        return None


__all__ = ["IndexStatus", "status_path", "save_status", "load_status"]
