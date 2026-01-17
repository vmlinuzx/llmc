# SDD: Migrate to watchfiles for File Watching

**Status:** ✅ COMPLETE  
**Author:** Dave + Antigravity  
**Created:** 2026-01-16  
**Priority:** P2  
**Effort:** 4-6 hours  
**Difficulty:** 🟢 Easy

## 1. Problem Statement

### Current State

The RAG daemon uses `pyinotify` for file watching in `llmc/rag/watcher.py`:

| Issue | Impact |
|-------|--------|
| **Linux-only** | Cannot run daemon on macOS (dev machines) |
| **Unmaintained** | Last pyinotify release: 2018 |
| **Verbose API** | Manual `WatchManager`, `ThreadedNotifier`, event masks |
| **Edge-case bugs** | Reported issues with recursive watching, symlinks |

### Desired State

Replace with `watchfiles` by Samuel Colvin (Pydantic author):

| Benefit | Description |
|---------|-------------|
| **Cross-platform** | Linux (inotify), macOS (FSEvents), Windows (ReadDirectoryChangesW) |
| **Rust core** | 10-100x faster than Python-based watchers |
| **Simple API** | Single iterator-based interface |
| **Active maintenance** | Regular releases, well-tested |
| **Already in deps** | Listed in `requirements.txt`, just not wired in |

---

## 2. Current Implementation Analysis

### File: `llmc/rag/watcher.py` (257 lines)

```
┌─────────────────────────────────────────────────────────────────┐
│                        watcher.py                                │
├─────────────────────────────────────────────────────────────────┤
│  FileFilter          │ Gitignore-aware path filtering           │
│  ChangeQueue         │ Debounced queue of repos with changes    │
│  RepoWatcher         │ Watches single repo via inotify          │
│  _InotifyHandler     │ Internal pyinotify event handler         │
│  is_inotify_available│ Availability check                       │
│  get_inotify_watch_limit │ Read /proc limit                     │
└─────────────────────────────────────────────────────────────────┘
```

### Key Classes

#### `FileFilter` (lines 63-108)
- Loads `.gitignore` patterns via `pathspec`
- Hardcoded `ALWAYS_IGNORE` set (`.git`, `node_modules`, `__pycache__`, etc.)
- `should_ignore(path) -> bool`

**Migration:** Keep as-is, wrap in watchfiles `DefaultFilter` subclass.

#### `ChangeQueue` (lines 111-162)
- Thread-safe debouncing queue
- `add(repo_path)` → records timestamp
- `get_ready()` → returns repos stable for N seconds
- `wait(timeout)` → blocks until changes

**Migration:** Keep unchanged. watchfiles doesn't have built-in debouncing.

#### `RepoWatcher` (lines 165-228)
- Creates `pyinotify.WatchManager` and `ThreadedNotifier`
- Watches: `IN_MODIFY | IN_CREATE | IN_DELETE | IN_MOVED_FROM | IN_MOVED_TO`
- Recursive with `auto_add=True`
- Callback: `on_change(path: Path)`

**Migration:** Replace internals with watchfiles iterator in thread.

#### `_InotifyHandler` (lines 231-242)
- Extends `pyinotify.ProcessEvent`
- Routes events to `RepoWatcher._handle_event()`

**Migration:** Delete. watchfiles uses iterator, not callbacks.

### Consumer: `llmc/rag/service.py` (lines 766-850)

```python
# Current usage pattern
queue = ChangeQueue(debounce_seconds=2.0)
watchers: list[RepoWatcher] = []

for repo_path in self.state.state["repos"]:
    watcher = RepoWatcher(
        repo,
        lambda p, r=repo_path: queue.add(r),  # callback
        FileFilter(repo),
    )
    watcher.start()
    watchers.append(watcher)

# Main loop
while self.running:
    queue.wait(timeout=5.0)
    ready_repos = queue.get_ready()
    for repo in ready_repos:
        self.process_repo(repo)

# Cleanup
for watcher in watchers:
    watcher.stop()
```

**Migration:** Interface unchanged. `RepoWatcher.start()/.stop()` still work.

---

## 3. Target Implementation

### 3.1 Event Type Mapping

| pyinotify | watchfiles | Semantic |
|-----------|------------|----------|
| `IN_CREATE` | `Change.added` | File created |
| `IN_MODIFY` | `Change.modified` | File changed |
| `IN_DELETE` | `Change.deleted` | File deleted |
| `IN_MOVED_FROM` | `Change.deleted` | Source of move |
| `IN_MOVED_TO` | `Change.added` | Destination of move |

### 3.2 New `RepoWatcher` Implementation

```python
from watchfiles import watch, Change, DefaultFilter
import threading
from pathlib import Path
from typing import Callable

class LLMCFilter(DefaultFilter):
    """Combines watchfiles defaults with LLMC-specific ignores."""
    
    def __init__(self, file_filter: FileFilter):
        super().__init__()
        self.file_filter = file_filter
    
    def __call__(self, change: Change, path: str) -> bool:
        # Use parent's filtering (ignores .git, __pycache__, etc.)
        if not super().__call__(change, path):
            return False
        # Apply our gitignore-aware filter
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
        """Internal loop running in background thread."""
        watch_filter = LLMCFilter(self.file_filter)
        
        for changes in watch(
            self.repo_path,
            watch_filter=watch_filter,
            stop_event=self._stop_event,
            recursive=True,
        ):
            for change_type, path in changes:
                self.on_change(Path(path))


def is_watchfiles_available() -> bool:
    """Check if watchfiles is available."""
    try:
        import watchfiles
        return True
    except ImportError:
        return False
```

### 3.3 Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Sync vs Async** | Sync (`watch()`) in thread | Matches current threading model, minimal change to service.py |
| **Stop mechanism** | `stop_event` parameter | Built into watchfiles, clean shutdown |
| **Keep ChangeQueue** | Yes | watchfiles has no debouncing, our queue works well |
| **Keep FileFilter** | Yes | Wrap in `LLMCFilter`, preserves gitignore logic |
| **Thread per repo** | Yes | Same as current, one watcher per repo |

### 3.4 Backward Compatibility

The public interface is unchanged:

```python
# Before and after - identical usage
watcher = RepoWatcher(repo_path, on_change_callback, file_filter)
watcher.start()
# ... 
watcher.stop()
```

---

## 4. Migration Plan

### Phase 1: Core Migration (2-3 hours)

| Task | Description |
|------|-------------|
| 1.1 | Replace `RepoWatcher` internals with watchfiles |
| 1.2 | Create `LLMCFilter` extending `DefaultFilter` |
| 1.3 | Delete `_InotifyHandler` class |
| 1.4 | Update `is_inotify_available()` → `is_watchfiles_available()` |
| 1.5 | Remove `get_inotify_watch_limit()` (watchfiles handles this) |

### Phase 2: Cleanup (30 min)

| Task | Description |
|------|-------------|
| 2.1 | Remove pyinotify from `pyproject.toml` |
| 2.2 | Remove pyinotify from `requirements.txt` |
| 2.3 | Update docstrings and module docstring |

### Phase 3: Testing (1-2 hours)

| Task | Description |
|------|-------------|
| 3.1 | Update `test_watcher_fix.py` for watchfiles |
| 3.2 | Add integration test: create/modify/delete detection |
| 3.3 | Add test: gitignore filtering works |
| 3.4 | Add test: graceful stop within timeout |
| 3.5 | Manual test on macOS (if available) |

### Phase 4: Verification (30 min)

| Task | Description |
|------|-------------|
| 4.1 | Run `llmc rag daemon` and verify file watching works |
| 4.2 | Create/modify/delete files, verify `process_repo()` called |
| 4.3 | Check logs for any watchfiles errors |

---

## 5. Files Changed

| File | Change |
|------|--------|
| `llmc/rag/watcher.py` | Replace pyinotify with watchfiles |
| `pyproject.toml` | Remove `pyinotify` from deps |
| `requirements.txt` | Remove `pyinotify` line |
| `tests/ruthless/test_watcher_fix.py` | Update for watchfiles |
| `tests/rag/test_watcher.py` | New integration tests |

---

## 6. Test Strategy

### Unit Tests

```python
def test_watchfiles_available():
    """Verify watchfiles can be imported."""
    assert is_watchfiles_available()

def test_llmc_filter_ignores_git():
    """LLMCFilter should ignore .git directories."""
    filter_ = LLMCFilter(FileFilter(Path("/tmp/repo")))
    assert not filter_(Change.modified, "/tmp/repo/.git/config")

def test_llmc_filter_allows_python():
    """LLMCFilter should allow .py files."""
    filter_ = LLMCFilter(FileFilter(Path("/tmp/repo")))
    assert filter_(Change.modified, "/tmp/repo/main.py")
```

### Integration Tests

```python
def test_watcher_detects_create(tmp_path):
    """RepoWatcher should detect file creation."""
    changes = []
    watcher = RepoWatcher(tmp_path, lambda p: changes.append(p))
    watcher.start()
    
    (tmp_path / "test.py").write_text("# new file")
    time.sleep(0.5)
    
    watcher.stop()
    assert any("test.py" in str(p) for p in changes)

def test_watcher_stops_gracefully(tmp_path):
    """RepoWatcher.stop() should complete within timeout."""
    watcher = RepoWatcher(tmp_path, lambda p: None)
    watcher.start()
    
    start = time.time()
    watcher.stop()
    elapsed = time.time() - start
    
    assert elapsed < 3.0  # Should stop quickly
```

---

## 7. Rollback Plan

If issues discovered post-migration:

1. `git revert` the migration commit
2. Re-add pyinotify to deps
3. Document the issue for future fix

Risk is low because:
- watchfiles is well-tested (used by uvicorn, FastAPI ecosystem)
- Interface unchanged, only internals replaced
- Can test on Linux before removing pyinotify fallback

---

## 8. Open Questions

| Question | Answer |
|----------|--------|
| Keep pyinotify as fallback? | No. watchfiles works on Linux too, no need for two codepaths. |
| What about `scripts/rag/watch_workspace.py`? | Uses `watchdog`, separate concern. Could migrate later if desired. |
| Async support needed? | Not now. Current threading model works. Could add `awatch` later if service.py goes async. |

---

## 9. References

- [watchfiles GitHub](https://github.com/samuelcolvin/watchfiles)
- [watchfiles docs](https://watchfiles.helpmanual.io/)
- [pyinotify (archived)](https://github.com/seb-m/pyinotify)
- Roadmap item: 2.13 Migrate to watchfiles for File Watching
