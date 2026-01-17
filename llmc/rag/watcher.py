"""
Event-driven file watching for LLMC RAG Service.

Uses watchfiles to watch repos for file changes, triggering
processing only when files actually change. This eliminates the
CPU-wasting polling loop.

Architecture:
- RepoWatcher: Watches a single repo directory via watchfiles
- ChangeQueue: Debounced queue of repos with pending changes
- FileFilter: Gitignore-aware path filtering
"""

from __future__ import annotations

from collections.abc import Callable
import logging
from pathlib import Path
import threading
import time

import pathspec

# Gracefully handle missing watchfiles dependency
try:
    from watchfiles import Change, DefaultFilter, watch

    WATCHFILES_AVAILABLE = True
except ImportError:
    WATCHFILES_AVAILABLE = False

    # Stub types to prevent NameError when watchfiles is not installed
    class DefaultFilter:  # type: ignore[no-redef]
        """Stub for watchfiles.DefaultFilter when watchfiles is not installed."""

        pass

    Change = None  # type: ignore[misc,assignment]
    watch = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

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
            self._pending[repo_path] = time.monotonic()
            self._event.set()

    def get_ready(self) -> list[str]:
        """Return repos that have been stable for debounce_seconds."""
        now = time.monotonic()
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


class LLMCFilter(DefaultFilter):
    """Combines watchfiles defaults with LLMC-specific ignores."""

    def __init__(self, file_filter: FileFilter):
        super().__init__()
        self.file_filter = file_filter

    def __call__(self, change: Change, path: str) -> bool:
        if not super().__call__(change, path):
            return False
        return not self.file_filter.should_ignore(Path(path))


class RepoWatcher:
    """Watches a single repo for file changes via watchfiles.

    When a relevant file changes, calls the on_change callback.
    Filters out noise (.git, __pycache__, etc.).
    """

    def __init__(
        self,
        repo_path: Path,
        on_change: Callable[[Path], None],
        filter_: FileFilter | None = None,
    ):
        if not WATCHFILES_AVAILABLE:
            raise RuntimeError(
                "watchfiles is not installed. "
                "Install it with: pip install watchfiles"
            )

        self.repo_path = repo_path.resolve()
        self.on_change = on_change
        self.file_filter = filter_ or FileFilter(self.repo_path)

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        """Start watching (non-blocking, runs in background thread)."""
        if self._running:
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._watch_loop,
            daemon=True,
            name=f"watcher-{self.repo_path.name}",
        )
        self._thread.start()
        self._running = True

    def stop(self) -> None:
        """Stop watching and clean up."""
        if not self._running:
            return

        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._running = False

    def _watch_loop(self) -> None:
        watch_filter = LLMCFilter(self.file_filter)

        for changes in watch(
            self.repo_path,
            watch_filter=watch_filter,
            stop_event=self._stop_event,
            recursive=True,
        ):
            for _change_type, path in changes:
                try:
                    self.on_change(Path(path))
                except Exception:
                    logger.exception("Error handling file change: %s", path)


def is_watchfiles_available() -> bool:
    """Check if watchfiles is available on this system."""
    return WATCHFILES_AVAILABLE
