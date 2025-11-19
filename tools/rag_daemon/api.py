from __future__ import annotations

"""
Public-facing helpers for daemon job submission and path validation.

Group 3 focuses on ingress path safety: any repo/workspace paths provided
to the daemon should be normalized and constrained relative to configured
roots using safe_subpath.
"""

from pathlib import Path
from typing import Any, Optional, Tuple

from tools.rag_repo.fs import SafeFS
from tools.rag_repo.utils import PathTraversalError, canonical_repo_path, safe_subpath


def validate_job_paths(
    config: Any,
    raw_repo_path: str | Path,
    raw_workspace_path: str | Path | None = None,
) -> Tuple[Path, Optional[Path]]:
    """
    Validate and normalize job paths according to DaemonConfig-like roots.

    If config.repos_root or config.workspaces_root are set, route through
    safe_subpath; otherwise fall back to canonical_repo_path.
    """
    if getattr(config, "repos_root", None) is not None:
        repo_path = safe_subpath(Path(config.repos_root), raw_repo_path)
    else:
        repo_path = canonical_repo_path(Path(raw_repo_path))

    workspace_path: Optional[Path] = None
    if raw_workspace_path is not None:
        if getattr(config, "workspaces_root", None) is not None:
            workspace_path = safe_subpath(Path(config.workspaces_root), raw_workspace_path)
        else:
            workspace_path = canonical_repo_path(Path(raw_workspace_path))

    return repo_path, workspace_path


def purge_workspace(config: Any, raw_workspace_path: str | Path, *, force: bool = False) -> dict:
    """Purge a workspace via daemon API. Requires force=True."""
    if not force:
        raise RuntimeError("Refusing to purge without force=True")
    # Use validate_job_paths to normalize the workspace path; repo path is unused here.
    _, workspace = validate_job_paths(
        config,
        raw_repo_path=canonical_repo_path(Path("/dev/null")),
        raw_workspace_path=raw_workspace_path,
    )
    fs = SafeFS(workspace)
    fs.rm_tree(".")
    return {"workspace_root": workspace}
