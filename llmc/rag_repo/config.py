"""Global tool config for the repo registration tool."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import]
except Exception:  # pragma: no cover - optional
    yaml = None  # type: ignore[assignment]

from .models import ToolConfig


def _expand(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def load_tool_config(path: str | None = None) -> ToolConfig:
    """Load tool config from YAML (or return defaults)."""
    if path is None:
        path = os.environ.get("LLMC_RAG_REPO_CONFIG", "~/.llmc/registry-config.yml")

    cfg_path = _expand(path)
    if not cfg_path.exists() or yaml is None:
        registry_path = _expand("~/.llmc/repos.yml")
        return ToolConfig(
            registry_path=registry_path,
            daemon_control_path=_expand("~/.llmc/rag-control/"),
        )

    with cfg_path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    registry_path = _expand(raw.get("registry_path", "~/.llmc/repos.yml"))
    daemon_control = raw.get("daemon_control_path", "~/.llmc/rag-control/")

    return ToolConfig(
        registry_path=registry_path,
        default_workspace_folder_name=raw.get(
            "default_workspace_folder_name", ".llmc/rag"
        ),
        default_rag_profile=raw.get("default_rag_profile", "default"),
        daemon_control_path=_expand(daemon_control),
        log_level=str(raw.get("log_level", "INFO")),
    )
