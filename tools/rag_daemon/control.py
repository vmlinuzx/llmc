"""Flag-file based control surface for the daemon."""

from __future__ import annotations

from pathlib import Path
from typing import Set

from .models import ControlEvents


def read_control_events(control_dir: Path) -> ControlEvents:
    """Scan control directory and return control events."""
    refresh_all = False
    refresh_repo_ids: Set[str] = set()
    shutdown = False

    if not control_dir.exists():
        return ControlEvents()

    for path in control_dir.glob("*.flag"):
        name = path.name
        if name == "refresh_all.flag":
            refresh_all = True
        elif name == "shutdown.flag":
            shutdown = True
        elif name.startswith("refresh_") and name.endswith(".flag"):
            repo_id = name[len("refresh_") : -len(".flag")]
            if repo_id:
                refresh_repo_ids.add(repo_id)

        try:
            path.unlink()
        except Exception:
            # Non-fatal if we fail to delete
            pass

    return ControlEvents(refresh_all=refresh_all, refresh_repo_ids=refresh_repo_ids, shutdown=shutdown)
