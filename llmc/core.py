from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

LLMC_VERSION = "0.5.5"  # TODO: Sync with pyproject.toml


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

    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        # Return empty config on error for now, let caller handle
        return {}
