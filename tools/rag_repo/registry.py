"""Repo registry adapter shared with the daemon."""

from __future__ import annotations

import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml  # type: ignore[import]
except Exception:  # pragma: no cover - optional
    yaml = None  # type: ignore[assignment]

from .models import RegistryEntry, ToolConfig
from .utils import canonical_repo_path


class RegistryAdapter:
    """YAML-based registry of repos for LLMC RAG."""

    def __init__(self, config: ToolConfig | Path) -> None:
        """Create an adapter from a ToolConfig or direct path."""
        if isinstance(config, Path):
            self.path = config
        else:
            self.path = config.registry_path

    def load_all(self) -> Dict[str, RegistryEntry]:
        if yaml is None or not self.path.exists():
            return {}

        with self.path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        entries: Dict[str, RegistryEntry] = {}
        for repo_id, data in raw.items():
            entries[repo_id] = RegistryEntry(
                repo_id=repo_id,
                repo_path=canonical_repo_path(Path(os.path.expanduser(data["repo_path"]))),
                rag_workspace_path=canonical_repo_path(
                    Path(os.path.expanduser(data["rag_workspace_path"]))
                ),
                display_name=data.get("display_name", repo_id),
                rag_profile=data.get("rag_profile", "default"),
                tags=list(data.get("tags", [])),
                created_at=datetime.fromisoformat(
                    data.get("created_at", datetime.utcnow().isoformat())
                ),
                updated_at=datetime.fromisoformat(
                    data.get("updated_at", datetime.utcnow().isoformat())
                ),
                min_refresh_interval_seconds=data.get("min_refresh_interval_seconds"),
            )

        return entries

    def save_all(self, entries: Dict[str, RegistryEntry]) -> None:
        if yaml is None:
            raise RuntimeError("PyYAML is required to write the repo registry")

        payload = {}
        for repo_id, entry in entries.items():
            data = asdict(entry)
            data["repo_path"] = str(entry.repo_path)
            data["rag_workspace_path"] = str(entry.rag_workspace_path)
            data["created_at"] = entry.created_at.isoformat()
            data["updated_at"] = entry.updated_at.isoformat()
            payload[repo_id] = data

        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f)
        tmp.replace(self.path)

    def register(self, entry: RegistryEntry) -> None:
        entries = self.load_all()
        entries[entry.repo_id] = entry
        entry.updated_at = datetime.utcnow()
        self.save_all(entries)

    def unregister_by_id(self, repo_id: str) -> bool:
        entries = self.load_all()
        if repo_id not in entries:
            return False
        entries.pop(repo_id)
        self.save_all(entries)
        return True

    def list_entries(self) -> List[RegistryEntry]:
        return list(self.load_all().values())

    def find_by_path(self, repo_path: Path) -> Optional[RegistryEntry]:
        canonical = canonical_repo_path(repo_path)
        for entry in self.load_all().values():
            if canonical == canonical_repo_path(entry.repo_path):
                return entry
        return None

    def find_by_id(self, repo_id: str) -> Optional[RegistryEntry]:
        return self.load_all().get(repo_id)
