from pathlib import Path
import tomllib
from typing import Any

LLMC_VERSION = "0.8.1"  # Hotdog Water release - Dec 2025


def find_repo_root(start_path: Path | None = None) -> Path:
    """
    Find the repository root by looking for .llmc/ or .git/ directories.
    """
    if start_path is None:
        start_path = Path(".")
    current = start_path.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".llmc").is_dir():
            return parent
        if (parent / ".git").is_dir():
            return parent

    # Fallback: return current directory (will likely fail later if not initialized)
    return current


def load_config(repo_root: Path | None = None) -> dict[str, Any]:
    """
    Load llmc.toml from the repository root.
    """
    if repo_root is None:
        repo_root = find_repo_root()

    config_path = repo_root / "llmc.toml"
    if not config_path.exists():
        return {}

    with open(config_path, "rb") as f:
        return tomllib.load(f)
