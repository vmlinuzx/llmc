from pathlib import Path
import tomllib
from typing import Any

LLMC_VERSION = "0.6.4"  # Bad Mojo release - Dec 2025


def find_repo_root(start_path: Path = Path(".")) -> Path:
    """
    Find the repository root by looking for .llmc/ or .git/ directories.
    """
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
