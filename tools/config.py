from __future__ import annotations

from pathlib import Path
from typing import Any

from .rag.config import load_config


def get_llmc_config(repo_root: Path | None = None) -> dict[str, Any]:
    """
    Load the llmc.toml configuration for the given repository root.

    This is a thin wrapper around tools.rag.config.load_config used by
    EmbeddingManager and other components that expect a global config loader.
    """
    return load_config(repo_root)

