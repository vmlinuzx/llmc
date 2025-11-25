"""Config loader for the LLMC RAG Daemon."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml  # type: ignore[import]
except Exception:  # pragma: no cover - optional dependency
    yaml = None  # type: ignore[assignment]

from .models import DaemonConfig


def _expand(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def load_config(path: Optional[str] = None) -> DaemonConfig:
    """Load daemon config from YAML."""
    if path is None:
        path = os.environ.get("LLMC_RAG_DAEMON_CONFIG", "~/.llmc/rag-daemon.yml")

    cfg_path = _expand(path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Daemon config not found at {cfg_path}")

    if yaml is None:
        raise RuntimeError("PyYAML is required to load daemon config")

    with cfg_path.open("r", encoding="utf-8") as f:
        raw: Dict[str, Any] = yaml.safe_load(f) or {}

    def get_int(key: str, default: int) -> int:
        return int(raw.get(key, default))

    def get_str(key: str, default: str) -> str:
        return str(raw.get(key, default))

    cfg = DaemonConfig(
        tick_interval_seconds=get_int("tick_interval_seconds", 120),
        max_concurrent_jobs=get_int("max_concurrent_jobs", 2),
        max_consecutive_failures=get_int("max_consecutive_failures", 5),
        base_backoff_seconds=get_int("base_backoff_seconds", 60),
        max_backoff_seconds=get_int("max_backoff_seconds", 3600),
        registry_path=_expand(raw.get("registry_path", "~/.llmc/repos.yml")),
        state_store_path=_expand(raw.get("state_store_path", "~/.llmc/rag-state/")),
        log_path=_expand(raw.get("log_path", "~/.llmc/logs/rag-daemon/")),
        control_dir=_expand(raw.get("control_dir", "~/.llmc/rag-control/")),
        job_runner_cmd=get_str("job_runner_cmd", "llmc-rag-job"),
        log_level=get_str("log_level", "INFO"),
    )

    # Ensure important directories exist
    cfg.state_store_path.mkdir(parents=True, exist_ok=True)
    cfg.log_path.mkdir(parents=True, exist_ok=True)
    cfg.control_dir.mkdir(parents=True, exist_ok=True)

    return cfg
