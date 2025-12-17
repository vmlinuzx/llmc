"""Repo registry client for the LLMC RAG Daemon."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import]
except Exception:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore[assignment]

from ..rag_repo.utils import PathTraversalError, safe_subpath
from .models import DaemonConfig, RepoDescriptor


def _normalize_paths(
    config: Any,
    raw_repo_path: str | Path,
    raw_workspace_path: str | Path | None,
) -> tuple[Path, Path | None]:
    """
    Normalize and constrain paths according to DaemonConfig-like roots.

    If `config.repos_root` or `config.workspaces_root` are set, route paths
    through safe_subpath; otherwise fall back to simple expanduser/resolve.
    """

    def _canon(p: Path | str) -> Path:
        return Path(p).expanduser().resolve()

    repos_root = getattr(config, "repos_root", None)
    if repos_root is not None:
        repo_base = Path(repos_root)
        repo_path = safe_subpath(repo_base, raw_repo_path)
    else:
        repo_path = _canon(raw_repo_path)

    workspace_path: Path | None = None
    if raw_workspace_path is not None:
        workspaces_root = getattr(config, "workspaces_root", None)
        if workspaces_root is not None:
            ws_base = Path(workspaces_root)
            workspace_path = safe_subpath(ws_base, raw_workspace_path)
        else:
            workspace_path = _canon(raw_workspace_path)

    return repo_path, workspace_path


def _iter_entries(data: object) -> Iterable[tuple[str, dict]]:
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


class RegistryError(ValueError):
    """Raised when the registry payload cannot be parsed or validated."""


@dataclass
class RegistryClient:
    """Read-only view over the shared repo registry."""

    path: Path
    config: DaemonConfig | None = None

    @classmethod
    def from_config(cls, config: DaemonConfig) -> RegistryClient:
        return cls(path=Path(config.registry_path), config=config)

    def _read_payload(self) -> Any:
        """Read and parse the registry YAML, raising on malformed input."""
        reg_path = Path(self.path)
        if not reg_path.exists():
            return {}

        if yaml is not None:
            with reg_path.open("r", encoding="utf-8") as handle:
                try:
                    return yaml.safe_load(handle) or {}
                except yaml.YAMLError as exc:  # type: ignore[attr-defined]
                    raise RegistryError(f"Malformed registry YAML: {exc}") from exc
        # Minimal fallback parser when PyYAML is unavailable.
        text = reg_path.read_text(encoding="utf-8")
        result: dict[str, dict[str, str]] = {}
        current: str | None = None
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if not line:
                continue
            if not line.startswith(" "):
                if ":" in line:
                    current = line.split(":", 1)[0].strip()
                    result[current] = {}
                continue
            if current is None:
                continue
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            result[current][key.strip()] = value.strip().strip('"').strip("'")
        return result

    def _resolve_path(self, raw_path: str | Path) -> Path:
        """Expand/resolve a user-provided path with safety guards."""
        try:
            text = str(raw_path)
        except Exception as exc:  # pragma: no cover - defensive
            raise RegistryError(f"Invalid path entry: {raw_path!r}") from exc

        if "\x00" in text:
            raise RegistryError("Registry paths may not contain NUL bytes")

        expanded = Path(text).expanduser()
        try:
            resolved = expanded.resolve()
        except Exception as exc:
            raise RegistryError(f"Unable to resolve path {text!r}") from exc

        if ".." in Path(text).parts:
            raise PathTraversalError(f"Path traversal blocked: {text!r}")

        if not _is_safe_path(resolved):
            raise PathTraversalError(f"Unsafe path rejected: {resolved}")

        return resolved

    def load(self) -> dict[str, RepoDescriptor]:
        """Return a mapping of repo_id → RepoDescriptor.

        Tolerates missing YAML or optional PyYAML. Invalid entries are skipped.
        """
        result: dict[str, RepoDescriptor] = {}
        reg_path = Path(self.path)
        if not reg_path.exists():
            return result

        data = self._read_payload()
        if not data:
            return result

        entries_seen = 0
        missing_required = False

        for repo_id, entry in _iter_entries(data):
            entries_seen += 1
            try:
                descriptor = self._entry_to_descriptor(repo_id, entry)
            except KeyError:
                missing_required = True
                continue
            except (PathTraversalError, RegistryError):
                # Security: drop traversal attempts silently so callers only see safe repos.
                continue
            result[repo_id] = descriptor

        if result or entries_seen == 0:
            return result
        if missing_required:
            raise KeyError("Registry entries missing required fields")
        return result

    def _entry_to_descriptor(self, repo_id: str, entry: dict) -> RepoDescriptor:
        """Validate an entry and return a RepoDescriptor."""
        raw_repo_path = entry.get("repo_path")
        raw_workspace_path = entry.get("rag_workspace_path")
        if raw_repo_path is None:
            raise KeyError("repo_path is required")
        if raw_workspace_path is None:
            raise KeyError("rag_workspace_path is required")

        if self.config is not None:
            repo_path, workspace_candidate = _normalize_paths(
                self.config, raw_repo_path, raw_workspace_path
            )
            if workspace_candidate is None:
                raise KeyError("rag_workspace_path is required")
            workspace_path = workspace_candidate
        else:
            repo_path = self._resolve_path(raw_repo_path)
            workspace_path = self._resolve_path(raw_workspace_path)

        display_name = entry.get("display_name") or repo_id
        rag_profile = entry.get("rag_profile") or "default"
        min_refresh = entry.get("min_refresh_interval_seconds")
        min_refresh_td = None
        if min_refresh is not None:
            try:
                min_refresh_td = timedelta(seconds=int(min_refresh))
            except Exception:
                min_refresh_td = None

        return RepoDescriptor(
            repo_id=repo_id,
            repo_path=repo_path,
            rag_workspace_path=workspace_path,
            display_name=display_name,
            rag_profile=rag_profile,
            min_refresh_interval=min_refresh_td,
        )
