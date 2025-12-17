from pathlib import Path
from typing import Any

from llmc.core import load_config as load_core_config

DEFAULT_ARTIFACT_DIR = "artifacts/ruta"


def get_ruta_config(repo_root: Path) -> dict[str, Any]:
    """Load RUTA configuration from llmc.toml."""
    cfg = load_core_config(repo_root)
    return cfg.get("ruta", {})


def get_artifact_dir(repo_root: Path) -> Path:
    """Get the directory for RUTA artifacts."""
    cfg = get_ruta_config(repo_root)
    rel_path = cfg.get("artifact_dir", DEFAULT_ARTIFACT_DIR)
    return repo_root / rel_path
