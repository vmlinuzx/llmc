from __future__ import annotations

from pathlib import Path
from typing import Any

from .cli import resolve_export_dir, resolve_workspace_from_cli


def doctor_paths(
    repo_root: Path | str,
    workspace_arg: Path | str | None = None,
    export_arg: Path | str | None = None,
) -> dict[str, Any]:
    """Quick checks for repo/workspace/export path sanity."""
    repo_root_path = Path(repo_root).expanduser().resolve()
    workspace_root = resolve_workspace_from_cli(repo_root_path, workspace_arg)
    export_dir = resolve_export_dir(repo_root_path, workspace_arg, export_arg or "exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    return {
        "repo_root": repo_root_path,
        "workspace_root": workspace_root,
        "export_dir": export_dir,
        "workspace_exists": workspace_root.exists(),
        "export_exists": export_dir.exists(),
        "export_empty": not any(export_dir.iterdir()),
        "under_workspace": str(export_dir).startswith(str(workspace_root)),
    }
