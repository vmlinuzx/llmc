"""Repo registry client for the LLMC RAG Daemon."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Dict

try:
    import yaml  # type: ignore[import]
except Exception:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore[assignment]

from .models import RepoDescriptor, DaemonConfig


@dataclass
class RegistryClient:
    """Read-only view over the shared repo registry."""

    path: Path

    @classmethod
    def from_config(cls, config: DaemonConfig) -> "RegistryClient":
        return cls(path=config.registry_path)

    def _is_safe_path(self, path: Path) -> bool:
        """Return True if path is not under sensitive system directories.

        This mitigates trivial path traversal via the registry by preventing
        repos from pointing at locations like /etc, /proc, /sys, /dev, /root.
        """
        try:
            path_resolved = path.resolve()
        except Exception:
            return False

        sensitive_roots = [
            Path("/etc"),
            Path("/proc"),
            Path("/sys"),
            Path("/dev"),
            Path("/root"),
        ]
        for root in sensitive_roots:
            try:
                path_resolved.relative_to(root)
                return False
            except ValueError:
                continue
        return True

    def load(self) -> Dict[str, RepoDescriptor]:
        """Load all repo descriptors from the registry file."""
        if yaml is None:
            raise RuntimeError("PyYAML is required to read the repo registry")

        if not self.path.exists():
            return {}

        with self.path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        result: Dict[str, RepoDescriptor] = {}
        # Support both legacy dict format (repo_id -> entry) and new
        # list-based format under a top-level "repos" key.
        if isinstance(data, dict) and isinstance(data.get("repos"), list):
            entries_iter = []
            for entry in data["repos"]:
                if not isinstance(entry, dict):
                    continue
                repo_id = entry.get("repo_id")
                if not repo_id:
                    continue
                entries_iter.append((repo_id, entry))
        elif isinstance(data, list):
            entries_iter = []
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                repo_id = entry.get("repo_id")
                if not repo_id:
                    continue
                entries_iter.append((repo_id, entry))
        elif isinstance(data, dict):
            entries_iter = list(data.items())
        else:
            entries_iter = []

        for repo_id, entry in entries_iter:
            raw_repo_path = entry["repo_path"]
            raw_workspace_path = entry["rag_workspace_path"]

            # Reject obvious traversal attempts based on raw path segments.
            try:
                if ".." in Path(str(raw_repo_path)).parts:
                    continue
                if ".." in Path(str(raw_workspace_path)).parts:
                    continue
            except Exception:
                continue

            repo_path = Path(os.path.expanduser(raw_repo_path)).resolve()
            workspace_path = Path(
                os.path.expanduser(raw_workspace_path)
            ).resolve()

            # Security: only accept paths under user-controlled roots.
            if not self._is_safe_path(repo_path) or not self._is_safe_path(
                workspace_path
            ):
                continue

            display_name = entry.get("display_name")
            rag_profile = entry.get("rag_profile")
            min_refresh = entry.get("min_refresh_interval_seconds")
            min_refresh_td = None
            if min_refresh is not None:
                min_refresh_td = timedelta(seconds=int(min_refresh))

            result[repo_id] = RepoDescriptor(
                repo_id=repo_id,
                repo_path=repo_path,
                rag_workspace_path=workspace_path,
                display_name=display_name,
                rag_profile=rag_profile,
                min_refresh_interval=min_refresh_td,
            )

        return result
