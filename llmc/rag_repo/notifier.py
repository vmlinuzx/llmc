"""Daemon notifier for repo registration events."""

from __future__ import annotations

from .models import RegistryEntry, ToolConfig


def notify_refresh(entry: RegistryEntry, config: ToolConfig) -> None:
    """Best-effort nudge to the RAG daemon to refresh a repo soon."""
    if config.daemon_control_path is None:
        return
    control_dir = config.daemon_control_path
    control_dir.mkdir(parents=True, exist_ok=True)
    flag_path = control_dir / f"refresh_{entry.repo_id}.flag"
    try:
        flag_path.write_text("", encoding="utf-8")
    except Exception:
        return


def notify_refresh_all(config: ToolConfig) -> None:
    if config.daemon_control_path is None:
        return
    control_dir = config.daemon_control_path
    control_dir.mkdir(parents=True, exist_ok=True)
    flag_path = control_dir / "refresh_all.flag"
    try:
        flag_path.write_text("", encoding="utf-8")
    except Exception:
        return
