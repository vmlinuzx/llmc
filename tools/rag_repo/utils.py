"""Utility helpers for the repo registration tool."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional


class PathTraversalError(ValueError):
    """Raised when a user-controlled path escapes an allowed root."""


def canonical_repo_path(path: Path) -> Path:
    return path.resolve()


def safe_subpath(base: Path, user_path: str | Path) -> Path:
    """Resolve a user-controlled path under a fixed base directory.

    - Expands ``"~"`` when ``user_path`` is a string.
    - Resolves symlinks.
    - Ensures the resulting path is within ``base``.
    - Raises :class:`PathTraversalError` if the path escapes ``base``.
    """
    base_resolved = base.expanduser().resolve()
    user = Path(user_path).expanduser()

    if user.is_absolute():
        candidate = user.resolve()
    else:
        candidate = (base_resolved / user).resolve()

    try:
        candidate.relative_to(base_resolved)
    except ValueError:
        raise PathTraversalError(f"Path traversal blocked: {user_path!r}")

    return candidate


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
