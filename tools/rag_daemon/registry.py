"""Repo registry client for the LLMC RAG Daemon."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Dict, Iterable, Tuple, Any

try:
    import yaml  # type: ignore[import]
except Exception:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore[assignment]

from .models import DaemonConfig, RepoDescriptor
from ..rag_repo.utils import PathTraversalError, safe_subpath


def _normalize_paths(config: Any, raw_repo_path: str | Path, raw_workspace_path: str | Path | None) -> Tuple[Path, Path | None]:
    """
    Normalize and constrain paths according to DaemonConfig-like roots.

    If `config.repos_root` or `config.workspaces_root` are set, route paths
    through safe_subpath; otherwise fall back to simple expanduser/resolve.
    """

    def _canon(p: Path | str) -> Path:
        return Path(p).expanduser().resolve()

    if getattr(config, "repos_root", None) is not None:
        repo_base = Path(getattr(config, "repos_root"))
        repo_path = safe_subpath(repo_base, raw_repo_path)
    else:
        repo_path = _canon(raw_repo_path)

    workspace_path: Path | None = None
    if raw_workspace_path is not None:
        if getattr(config, "workspaces_root", None) is not None:
            ws_base = Path(getattr(config, "workspaces_root"))
            workspace_path = safe_subpath(ws_base, raw_workspace_path)
        else:
            workspace_path = _canon(raw_workspace_path)

    return repo_path, workspace_path


def _iter_entries(data: object) -> Iterable[Tuple[str, dict]]:
    """
    Yield (repo_id, entry) pairs from the registry payload.

    Supports:
    - {"repos": [ {repo_id, ...}, ... ]}
    - [ {repo_id, ...}, ... ]
    - { "id": { ... }, ... }
    """
    if isinstance(data, dict) and isinstance(data.get("repos"), list):
        for entry in data["repos"]:
            if not isinstance(entry, dict):
                continue
            repo_id = entry.get("repo_id")
            if not repo_id:
                continue
            yield repo_id, entry
    elif isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                continue
            repo_id = entry.get("repo_id")
            if not repo_id:
                continue
            yield repo_id, entry
    elif isinstance(data, dict):
        for repo_id, entry in data.items():
            if not isinstance(entry, dict):
                continue
            yield str(repo_id), entry


def _is_safe_path(path: Path) -> bool:
    """Return True if path is not under sensitive system directories."""
    try:
        path_resolved = path.resolve()
    except Exception:
        return False

    sensitive_roots = [Path("/etc"), Path("/proc"), Path("/sys"), Path("/dev"), Path("/root")]
    for root in sensitive_roots:
        try:
            path_resolved.relative_to(root)
            return False
        except ValueError:
            continue
    return True


@dataclass
class RegistryClient:
    """Read-only view over the shared repo registry."""

    path: Path

    @classmethod
    def from_config(cls, config: DaemonConfig) -> "RegistryClient":
        return cls(path=Path(config.registry_path))

    def load(self) -> Dict[str, RepoDescriptor]:
        """Return a mapping of repo_id → RepoDescriptor.

        Tolerates missing YAML or optional PyYAML. Invalid entries are skipped.
        """
        result: Dict[str, RepoDescriptor] = {}
        reg_path = Path(self.path)
        if not reg_path.exists():
            return result

        raw_data: dict[str, dict]
        if yaml is not None:
            try:
                with reg_path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
            except Exception:
                return result
        else:
            # Minimal fallback parser: expects "id:\n  repo_path: ...\n"
            txt = reg_path.read_text(encoding="utf-8", errors="ignore")
            data = {}
            current: str | None = None
            for line in txt.splitlines():
                if not line.strip():
                    continue
                if not line.startswith(" "):
                    if ":" in line:
                        current = line.split(":", 1)[0].strip()
                        data[current] = {}
                elif current:
                    if ":" in line:
                        k, v = line.split(":", 1)
                        data[current][k.strip()] = v.strip().strip('"').strip("'")

        for repo_id, entry in _iter_entries(data):
            try:
                raw_repo_path = entry.get("repo_path")
                raw_workspace_path = entry.get("rag_workspace_path")
                if not raw_repo_path:
                    continue

                repo_path = Path(str(os.path.expanduser(str(raw_repo_path)))).resolve()
                workspace_path = (
                    Path(str(os.path.expanduser(str(raw_workspace_path)))).resolve()
                    if raw_workspace_path
                    else None
                )

                # Security: only reject obviously sensitive system locations.
                if not _is_safe_path(repo_path) or (workspace_path is not None and not _is_safe_path(workspace_path)):
                    continue

                display_name = entry.get("display_name") or repo_id
                rag_profile = entry.get("rag_profile") or "default"
                min_refresh = entry.get("min_refresh_interval_seconds")
                min_refresh_td = None
                if min_refresh is not None:
                    try:
                        min_refresh_td = timedelta(seconds=int(min_refresh))
                    except Exception:
                        min_refresh_td = None

                result[repo_id] = RepoDescriptor(
                    repo_id=repo_id,
                    repo_path=repo_path,
                    rag_workspace_path=workspace_path,
                    display_name=display_name,
                    rag_profile=rag_profile,
                    min_refresh_interval=min_refresh_td,
                )
            except Exception:
                # Ignore malformed entries; caller sees only valid descriptors.
                continue

        return result
