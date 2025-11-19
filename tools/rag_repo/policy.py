from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class PathPolicyError(ValueError):
    """Raised when a path violates a configured safety policy."""


def _default_denylist() -> tuple[str, ...]:
    """Return a tuple of OS-critical roots that should never be touched."""
    items = ["/etc", "/proc", "/sys", "/dev", "/run", "/var/run"]
    # Windows equivalents (best-effort; still resolved/normalized before checks).
    items += ["C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)"]
    return tuple(items)


@dataclass
class PathSafetyPolicy:
    """Path handling constraints applied by SafeFS and related helpers."""

    readonly: bool = False
    dry_run: bool = False
    follow_symlinks: bool = False
    denylist_prefixes: tuple[str, ...] = _default_denylist()


def enforce_policy(candidate: Path, policy: PathSafetyPolicy) -> Path:
    """
    Apply denylist checks to a resolved path and return it if allowed.

    Raises PathPolicyError for any path under a denylisted prefix.
    """
    cand = Path(candidate).expanduser().resolve()
    for prefix in policy.denylist_prefixes:
        if str(cand).startswith(prefix):
            raise PathPolicyError(f"Path '{cand}' is denied by policy prefix '{prefix}'")
    return cand

