"""
Handle store for Tool Envelope.

In-memory dict for session-scoped result storage.
No TTL. No eviction. No persistence. Session dies, handles die.
Add complexity when actually needed.
"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any
import uuid


@dataclass
class StoredResult:
    """A stored result with metadata."""

    data: Any
    cmd: str
    created: float
    total_size: int = 0  # Total bytes before truncation


# Global store - lives for process lifetime
_STORE: dict[str, StoredResult] = {}


def store(result: Any, cmd: str, total_size: int = 0) -> str:
    """Store a result and return its handle ID."""
    handle = f"res_{uuid.uuid4().hex[:12]}"
    _STORE[handle] = StoredResult(
        data=result,
        cmd=cmd,
        created=time.time(),
        total_size=total_size,
    )
    return handle


def load(handle: str) -> Any | None:
    """Load a stored result by handle ID."""
    entry = _STORE.get(handle)
    return entry.data if entry else None


def get_entry(handle: str) -> StoredResult | None:
    """Get full entry with metadata."""
    return _STORE.get(handle)


def clear() -> int:
    """Clear all stored results. Returns count cleared."""
    count = len(_STORE)
    _STORE.clear()
    return count


def list_handles() -> list[str]:
    """List all stored handle IDs."""
    return list(_STORE.keys())
