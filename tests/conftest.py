"""Pytest configuration for LLMC tests.

Ensures the repository root is on sys.path so imports like
`from tools.rag_daemon...` and `from tools.rag_repo...` work regardless
of how pytest is invoked.
"""

from __future__ import annotations

import sys
import builtins
from pathlib import Path


def _ensure_repo_root_on_path() -> None:
    """Add repo root to sys.path if missing."""
    repo_root = Path(__file__).resolve().parent.parent
    repo_str = str(repo_root)
    if repo_str not in sys.path:
        sys.path.insert(0, repo_str)


def _inject_registry_adapter_alias() -> None:
    """Expose RegistryAdapter as a global for tests that assume it."""
    try:
        from tools.rag_repo.registry import RegistryAdapter  # type: ignore
    except Exception:
        return

    if not hasattr(builtins, "RegistryAdapter"):
        builtins.RegistryAdapter = RegistryAdapter  # type: ignore[attr-defined]


_ensure_repo_root_on_path()
_inject_registry_adapter_alias()

