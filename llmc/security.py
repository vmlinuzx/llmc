"""
Shared security utilities for LLMC.

This module provides path validation and security primitives used across
the codebase to prevent path traversal attacks and other security issues.
"""

from __future__ import annotations

from pathlib import Path


class PathSecurityError(ValueError):
    """Raised when path access is denied for security reasons."""

    pass


def normalize_path(repo_root: Path, target: str) -> Path:
    """Resolve target path relative to repo root, with fuzzy suffix matching.

    Security: Rejects paths outside repo_root to prevent path traversal attacks.

    Args:
        repo_root: The repository root directory (security boundary).
        target: The target path string (can be relative, absolute, or a suffix).

    Returns:
        Path relative to repo_root.

    Raises:
        PathSecurityError: If path is outside repo_root boundary or contains
            security-relevant characters (null bytes, etc.).

    Example:
        >>> normalize_path(Path("/repo"), "src/main.py")
        PosixPath('src/main.py')

        >>> normalize_path(Path("/repo"), "/repo/src/main.py")
        PosixPath('src/main.py')

        >>> normalize_path(Path("/repo"), "../../../etc/passwd")
        PathSecurityError: Path '../../../etc/passwd' escapes repository boundary...
    """
    # Security: Reject null bytes
    if "\x00" in target:
        raise PathSecurityError("Path contains null bytes")

    # 1. Try as exact path (relative or absolute)
    p = Path(target)
    if p.is_absolute():
        # Security: Absolute paths MUST be inside repo_root
        resolved = p.resolve()
        try:
            return resolved.relative_to(repo_root.resolve())
        except ValueError:
            raise PathSecurityError(
                f"Path '{target}' is outside repository boundary. "
                f"Only paths within {repo_root} are allowed."
            ) from None

    # Security: Check for traversal attempts (../)
    full_path = (repo_root / target).resolve()
    try:
        relative_path = full_path.relative_to(repo_root.resolve())
    except ValueError:
        raise PathSecurityError(
            f"Path '{target}' escapes repository boundary via traversal. "
            f"Only paths within {repo_root} are allowed."
        ) from None

    if full_path.exists():
        return relative_path

    # 2. Fuzzy Suffix Match
    # Find files in repo that end with the target string
    # This is a simple heuristic: find 'router.py' -> 'scripts/router.py'
    matches = []
    target_name = p.name

    # Walk repo (skip hidden/venv)
    for file in repo_root.rglob(f"*{target_name}"):
        if any(
            part.startswith(".") or part in ("venv", "__pycache__", "node_modules")
            for part in file.parts
        ):
            continue

        if str(file).endswith(target):
            try:
                matches.append(file.relative_to(repo_root))
            except ValueError:
                pass

    if not matches:
        return p  # Return original to fail downstream or be handled as symbol

    # Sort matches: shortest path length first, then alphabetical
    matches.sort(key=lambda m: (len(m.parts), str(m)))

    return matches[0]
