"""Utility helpers for the repo registration tool."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional


def canonical_repo_path(path: Path) -> Path:
    return path.resolve()


def generate_repo_id(repo_path: Path) -> str:
    """Generate a stable repo id based on canonical path."""
    canonical = str(canonical_repo_path(repo_path))
    digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()
    return f"repo-{digest[:12]}"


def is_git_repo(path: Path) -> bool:
    try:
        return (path / ".git").exists()
    except PermissionError:
        # Treat protected paths as "not a git repo" and let callers
        # surface a clearer permission error at the CLI boundary.
        return False


def read_text_if_exists(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")
