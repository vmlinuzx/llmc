"""Repo registry adapter shared with the daemon."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import os
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import]
except Exception:  # pragma: no cover - optional
    yaml = None  # type: ignore[assignment]

from .models import RegistryEntry, ToolConfig
from .utils import PathTraversalError, canonical_repo_path, safe_subpath


class RegistryAdapter:
    """YAML-based registry of repos for LLMC RAG."""

    def __init__(self, config: ToolConfig | Path) -> None:
        """Create an adapter from a ToolConfig or direct path."""
        if isinstance(config, Path):
            self.path = config
        else:
            self.path = config.registry_path

    def load_all(self) -> dict[str, RegistryEntry]:
        if yaml is None or not self.path.exists():
            return {}

        with self.path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        repo_docs: dict[str, dict] = {}
        if isinstance(raw, dict) and isinstance(raw.get("repos"), list):
            for item in raw["repos"]:
                if not isinstance(item, dict):
                    continue
                repo_id = item.get("repo_id")
                if repo_id:
                    repo_docs[repo_id] = item
        elif isinstance(raw, dict):
            repo_docs = {k: v for k, v in raw.items() if isinstance(v, dict)}

        entries: dict[str, RegistryEntry] = {}
        for repo_id, data in repo_docs.items():
            repo_raw = Path(os.path.expanduser(data["repo_path"]))
            repo_path = canonical_repo_path(repo_raw)

            raw_workspace = data.get("rag_workspace_path")
            try:
                if raw_workspace is None:
                    workspace_path = safe_subpath(repo_path, ".llmc/rag")
                else:
                    workspace_path = safe_subpath(repo_path, raw_workspace)
            except PathTraversalError:
                # Skip entries with unsafe workspace paths.
                continue

            entries[repo_id] = RegistryEntry(
                repo_id=repo_id,
                repo_path=repo_path,
                rag_workspace_path=workspace_path,
                display_name=data.get("display_name", repo_id),
                rag_profile=data.get("rag_profile", "default"),
                tags=list(data.get("tags", [])),
                created_at=datetime.fromisoformat(
                    data.get("created_at", datetime.now(UTC).isoformat())
                ),
                updated_at=datetime.fromisoformat(
                    data.get("updated_at", datetime.now(UTC).isoformat())
                ),
                min_refresh_interval_seconds=data.get("min_refresh_interval_seconds"),
            )

        return entries

    def save_all(self, entries: dict[str, RegistryEntry]) -> None:
        if yaml is None:
            raise RuntimeError("PyYAML is required to write the repo registry")

        timestamp = datetime.now(UTC).isoformat()
        serialized_entries: list[dict] = []
        for repo_id in sorted(entries):
            entry = entries[repo_id]
            data = asdict(entry)
            data["repo_id"] = repo_id
            data["repo_path"] = str(entry.repo_path)
            data["rag_workspace_path"] = str(entry.rag_workspace_path)
            data["created_at"] = entry.created_at.isoformat()
            data["updated_at"] = entry.updated_at.isoformat()
            serialized_entries.append(data)

        payload = {
            "version": 1,
            "config_version": "v1",
            "updated_at": timestamp,
            "repos": serialized_entries,
        }

        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f)
        tmp.replace(self.path)

    def register(self, entry: RegistryEntry) -> None:
        entries = self.load_all()
        existing = entries.get(entry.repo_id)
        if existing:
            entry.created_at = existing.created_at
        entry.updated_at = datetime.now(UTC)
        entries[entry.repo_id] = entry
        self.save_all(entries)

    def unregister_by_id(self, repo_id: str) -> bool:
        entries = self.load_all()
        if repo_id not in entries:
            return False
        entries.pop(repo_id)
        self.save_all(entries)
        return True

    def list_entries(self) -> list[RegistryEntry]:
        return list(self.load_all().values())

    def find_by_path(self, repo_path: Path) -> RegistryEntry | None:
        canonical = canonical_repo_path(repo_path)
        for entry in self.load_all().values():
            if canonical == canonical_repo_path(entry.repo_path):
                return entry
        return None

    def find_by_id(self, repo_id: str) -> RegistryEntry | None:
        return self.load_all().get(repo_id)


def _make_registry_entry_from_yaml(data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Helper for path-safety tests and future registry loaders.

    Validates the workspace path relative to the repo path using safe_subpath
    and returns a minimal dict describing the entry, or None if invalid.
    """
    raw_repo = data.get("repo_path")
    if not raw_repo:
        return None

    repo_path = canonical_repo_path(Path(os.path.expanduser(str(raw_repo))))
    raw_workspace = data.get("rag_workspace_path")

    try:
        if raw_workspace is None:
            workspace_path = safe_subpath(repo_path, ".llmc/workspace")
        else:
            workspace_path = safe_subpath(repo_path, raw_workspace)
    except PathTraversalError:
        return None

    name = data.get("name") or repo_path.name
    return {
        "name": name,
        "repo_path": repo_path,
        "rag_workspace_path": workspace_path,
    }


def load_registry_from_yaml(path: Path) -> list[dict[str, Any]]:
    """
    Lightweight loader used by path-safety tests.

    Supports the list-based `repos` format and returns only valid entries.
    """
    if yaml is None or not path.exists():
        return []

    with path.open("r", encoding="utf-8") as handle:
        doc = yaml.safe_load(handle) or {}

    if isinstance(doc, dict) and isinstance(doc.get("repos"), list):
        items = doc["repos"]
    elif isinstance(doc, list):
        items = doc
    else:
        items = []

    entries: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        entry = _make_registry_entry_from_yaml(item)
        if entry:
            entries.append(entry)
    return entries
