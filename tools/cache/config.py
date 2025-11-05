from __future__ import annotations

import os
from pathlib import Path

DEFAULT_CACHE_FILE = "semantic_cache.db"
DEFAULT_MIN_SCORE = 0.985
DEFAULT_MAX_RESULTS = 20
DEFAULT_MAX_AGE_SECONDS = 7 * 24 * 60 * 60  # one week
DEFAULT_MIN_OVERLAP = 0.6

_TRUTHY = {"1", "true", "yes", "on"}


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


def cache_enabled() -> bool:
    return not env_flag("SEMANTIC_CACHE_DISABLED", False)


def cache_db_path(repo_root: Path | None = None) -> Path:
    override = os.getenv("SEMANTIC_CACHE_DB")
    if override:
        path = Path(override).expanduser()
        if path.is_absolute():
            return path
        base = repo_root or Path.cwd()
        return (base / path).resolve()

    base_dir = os.getenv("SEMANTIC_CACHE_DIR")
    if base_dir:
        directory = Path(base_dir).expanduser()
    else:
        base = repo_root or Path.cwd()
        directory = (base / ".cache").resolve()
    return directory / DEFAULT_CACHE_FILE


def cache_min_score() -> float:
    raw = os.getenv("SEMANTIC_CACHE_MIN_SCORE")
    if raw is None:
        return DEFAULT_MIN_SCORE
    try:
        value = float(raw)
        if 0.0 < value <= 1.0:
            return value
    except ValueError:
        pass
    return DEFAULT_MIN_SCORE


def cache_max_age_seconds() -> int | None:
    raw = os.getenv("SEMANTIC_CACHE_MAX_AGE_SECONDS")
    if raw is None:
        return DEFAULT_MAX_AGE_SECONDS
    raw = raw.strip().lower()
    if raw in {"0", "none", "null", "disable"}:
        return None
    try:
        value = int(raw)
        if value > 0:
            return value
    except ValueError:
        pass
    return DEFAULT_MAX_AGE_SECONDS


def cache_max_results() -> int:
    raw = os.getenv("SEMANTIC_CACHE_MAX_RESULTS")
    if raw is None:
        return DEFAULT_MAX_RESULTS
    try:
        value = int(raw)
        if value > 0:
            return value
    except ValueError:
        pass
    return DEFAULT_MAX_RESULTS


def cache_min_overlap() -> float:
    raw = os.getenv("SEMANTIC_CACHE_MIN_OVERLAP")
    if raw is None:
        return DEFAULT_MIN_OVERLAP
    try:
        value = float(raw)
        if 0.0 <= value <= 1.0:
            return value
    except ValueError:
        pass
    return DEFAULT_MIN_OVERLAP
