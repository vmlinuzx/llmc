"""
Event-driven file watching for LLMC RAG Service.

Uses inotify (Linux) to watch repos for file changes, triggering
processing only when files actually change. This eliminates the
CPU-wasting polling loop.

Architecture:
- RepoWatcher: Watches a single repo directory via inotify
- ChangeQueue: Debounced queue of repos with pending changes
- FileFilter: Gitignore-aware path filtering
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
import threading
import time
from typing import Any

import pathspec

logger = logging.getLogger(__name__)

# inotify support (Linux only)
try:
    import pyinotify

    INOTIFY_AVAILABLE = True
    ProcessEvent = pyinotify.ProcessEvent
except ImportError:
    pyinotify = None  # type: ignore
    INOTIFY_AVAILABLE = False

    class ProcessEvent:  # type: ignore
        """Dummy class for when pyinotify is missing"""

        pass


# Directories to always ignore (fast path before gitignore check)
ALWAYS_IGNORE = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".rag",
        ".venv",
        "venv",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".next",
        ".cache",
    }
)


class FileFilter:
    """Filters file paths to ignore noise (git, caches, etc.)."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.spec = None
        self._load_gitignore()

    def _load_gitignore(self) -> None:
        """Load .gitignore patterns from repo root."""
        gitignore_path = self.repo_root / ".gitignore"
        patterns = []
        if gitignore_path.exists():
            try:
                with open(gitignore_path) as f:
                    patterns = list(f)
            except Exception as e:
                logger.warning("Failed to load .gitignore: %s", e)
                pass  # Ignore gitignore parse errors

        try:
            self.spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
        except Exception as e:
            logger.warning("Failed to parse .gitignore patterns: %s", e)
            # Fallback to empty spec if something goes wrong
            self.spec = pathspec.PathSpec.from_lines("gitwildmatch", [])

    def should_ignore(self, path: Path) -> bool:
        """Return True if path should be ignored."""
        # Quick reject: always-ignored directories
        parts = path.parts
        for part in parts:
            if part in ALWAYS_IGNORE:
                return True

        # Check gitignore patterns
        if self.spec:
            try:
                rel_path = path.relative_to(self.repo_root)
                # pathspec works best with string paths
                if self.spec.match_file(rel_path.as_posix()):
                    return True
            except ValueError:
                pass  # Path not relative to repo root

        return False


class ChangeQueue:
    """Debounced queue of repos with pending changes.

    When a file changes, the repo is added to the queue with a timestamp.
    `get_ready()` returns repos that have been stable for `debounce_seconds`.
    `wait()` blocks until there are pending changes.
    """

    def __init__(self, debounce_seconds: float = 2.0):
        self.debounce_seconds = debounce_seconds
        self._pending: dict[str, float] = {}  # repo_path -> last_change_time
        self._lock = threading.Lock()
        self._event = threading.Event()

    def add(self, repo_path: str) -> None:
        """Mark a repo as having pending changes."""
        with self._lock:
            self._pending[repo_path] = time.time()
            self._event.set()

    def get_ready(self) -> list[str]:
        """Return repos that have been stable for debounce_seconds."""
        now = time.time()
        with self._lock:
            ready = [
                path
                for path, ts in self._pending.items()
                if now - ts >= self.debounce_seconds
            ]
            for path in ready:
                del self._pending[path]
            if not self._pending:
                self._event.clear()
            return ready

    def has_pending(self) -> bool:
        """Check if any repos have pending changes."""
        with self._lock:
            return bool(self._pending)

    def wait(self, timeout: float | None = None) -> bool:
        """Block until there are pending changes or timeout.

        Returns True if woken by event, False if timeout.
        """
        return self._event.wait(timeout)

    def clear(self) -> None:
        """Clear all pending changes."""
        with self._lock:
            self._pending.clear()
            self._event.clear()


class RepoWatcher:
    """Watches a single repo for file changes via inotify.

    When a relevant file changes, calls the on_change callback.
    Filters out noise (.git, __pycache__, etc.).
    """

    def __init__(
        self,
        repo_path: Path,
        on_change: Callable[[Path], None],
        filter_: FileFilter | None = None,
    ):
        if not INOTIFY_AVAILABLE:
            raise RuntimeError(
                "pyinotify not available - install with: pip install pyinotify"
            )

        self.repo_path = repo_path.resolve()
        self.on_change = on_change
        self.filter = filter_ or FileFilter(self.repo_path)

        self._wm = pyinotify.WatchManager()
        self._handler = _InotifyHandler(self)
        self._notifier = pyinotify.ThreadedNotifier(self._wm, self._handler)
        self._running = False

    def start(self) -> None:
        """Start watching (non-blocking, runs in background thread)."""
        if self._running:
            return

        # Watch for modifications, creates, deletes, moves
        mask = (
            pyinotify.IN_MODIFY
            | pyinotify.IN_CREATE
            | pyinotify.IN_DELETE
            | pyinotify.IN_MOVED_FROM
            | pyinotify.IN_MOVED_TO
        )

        # Add recursive watch
        self._wm.add_watch(
            str(self.repo_path),
            mask,
            rec=True,
            auto_add=True,
        )

        self._notifier.start()
        self._running = True

    def stop(self) -> None:
        """Stop watching and clean up."""
        if not self._running:
            return

        self._notifier.stop()
        self._running = False

    def _handle_event(self, path: Path) -> None:
        """Handle a file change event (called by handler)."""
        if not self.filter.should_ignore(path):
            self.on_change(path)


class _InotifyHandler(ProcessEvent):
    """Internal handler for inotify events."""

    def __init__(self, watcher: RepoWatcher):
        super().__init__()
        self.watcher = watcher

    def process_default(self, event: Any) -> None:
        """Handle any inotify event."""
        if event.pathname:
            path = Path(event.pathname)
            self.watcher._handle_event(path)


def is_inotify_available() -> bool:
    """Check if inotify is available on this system."""
    return INOTIFY_AVAILABLE


def get_inotify_watch_limit() -> int | None:
    """Get the current inotify watch limit (Linux only)."""
    try:
        with open("/proc/sys/fs/inotify/max_user_watches") as f:
            return int(f.read().strip())
    except Exception:
        return None
