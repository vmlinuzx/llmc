# SDD: Event-Driven RAG Service

**Date:** 2025-12-11  
**Author:** Dave + Antigravity  
**Branch:** `feature/event-driven-service`  
**Status:** Draft

---

## 1. Problem Statement

The current RAG service (`tools/rag/service.py`) uses a **polling loop** that:

1. **Wastes CPU** - Runs at 180% CPU when idle because the loop spins continuously
2. **Inefficient multi-repo handling** - Processes all repos sequentially, then sleeps globally
3. **Delayed response** - Must wait for next poll cycle to detect changes (up to `interval` seconds)
4. **Broken idle backoff** - The backoff logic exists but doesn't prevent CPU waste when there's truly nothing to do

### Root Cause

The loop structure is fundamentally poll-based:
```python
while self.running:
    for repo in repos:
        self.process_repo(repo)  # Always runs, even if no changes
    time.sleep(interval)
```

When `process_repo()` returns quickly (no changes), the loop tight-spins.

---

## 2. Solution: Event-Driven Architecture

Replace polling with **inotify-based file watching**:

1. **Watch** registered repo directories for file changes
2. **Queue** changes with debouncing (wait 2s after last change)
3. **Sleep indefinitely** when queue is empty
4. **Wake instantly** when files change
5. **Process** only repos with pending changes

### Benefits

| Metric | Before (Polling) | After (Event-Driven) |
|--------|------------------|---------------------|
| Idle CPU | 180%+ | ~0% |
| Response latency | 0-180s (poll interval) | <3s (debounce) |
| Battery impact | High | Minimal |

---

## 3. Technical Design

### 3.1 Dependencies

- `pyinotify` (already installed) - Linux inotify wrapper
- Alternative: `watchdog` (cross-platform, but heavier)

### 3.2 Components

#### `RepoWatcher` Class
```python
class RepoWatcher:
    """Watches a single repo for file changes via inotify."""
    
    def __init__(self, repo_path: Path, on_change: Callable[[Path], None]):
        self.repo_path = repo_path
        self.on_change = on_change
        self._wm = pyinotify.WatchManager()
        self._notifier = pyinotify.Notifier(self._wm, self._handle_event)
        
    def start(self) -> None:
        """Start watching (non-blocking, adds to event loop)."""
        mask = pyinotify.IN_MODIFY | pyinotify.IN_CREATE | pyinotify.IN_DELETE
        self._wm.add_watch(str(self.repo_path), mask, rec=True, auto_add=True)
        
    def stop(self) -> None:
        """Stop watching."""
        self._notifier.stop()
```

#### `ChangeQueue` Class
```python
class ChangeQueue:
    """Debounced queue of repos with pending changes."""
    
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
                path for path, ts in self._pending.items()
                if now - ts >= self.debounce_seconds
            ]
            for path in ready:
                del self._pending[path]
            if not self._pending:
                self._event.clear()
            return ready
            
    def wait(self, timeout: float | None = None) -> bool:
        """Block until there are pending changes or timeout."""
        return self._event.wait(timeout)
```

#### Updated `RAGService.run_loop()`
```python
def run_loop(self, interval: int):
    """Event-driven service loop."""
    signal.signal(signal.SIGTERM, self.handle_signal)
    signal.signal(signal.SIGINT, self.handle_signal)
    
    # Initialize watchers for all registered repos
    queue = ChangeQueue(debounce_seconds=2.0)
    watchers = []
    for repo in self.state.state["repos"]:
        watcher = RepoWatcher(Path(repo), lambda p, r=repo: queue.add(r))
        watcher.start()
        watchers.append(watcher)
    
    print(f"🚀 RAG service started (PID {os.getpid()})")
    print(f"   Watching {len(watchers)} repos for changes")
    print(f"   Mode: event-driven (inotify)")
    
    # Initial processing of all repos (catch up on any pending work)
    for repo in self.state.state["repos"]:
        self.process_repo(repo)
    
    while self.running:
        # Block until changes or periodic check (for new repos, etc.)
        queue.wait(timeout=300)  # Wake every 5 min for housekeeping
        
        if not self.running:
            break
            
        # Get repos with debounced changes
        ready_repos = queue.get_ready()
        
        if ready_repos:
            for repo in ready_repos:
                if not self.running:
                    break
                self.process_repo(repo)
        else:
            # Periodic housekeeping (log rotation, vacuum check)
            self._periodic_housekeeping()
    
    # Cleanup
    for watcher in watchers:
        watcher.stop()
    
    self.state.set_stopped()
    print("👋 RAG service stopped")
```

### 3.3 Gitignore-Aware Filtering

The inotify watcher should respect `.gitignore` to avoid triggering on:
- `.git/` changes
- `node_modules/`
- `__pycache__/`
- `.rag/` (our own index)

```python
def _should_process_path(self, path: Path) -> bool:
    """Return True if path should trigger processing."""
    # Quick reject common noise
    parts = path.parts
    if any(p in {'.git', 'node_modules', '__pycache__', '.rag', '.venv'} for p in parts):
        return False
    # TODO: Full gitignore parsing via pathspec library
    return True
```

---

## 4. Migration Strategy

### Phase 1: Add Event-Driven Mode (This PR)
- Add `--mode event` flag to `llmc-rag start`
- Keep polling mode as `--mode poll` (current default)
- Test event mode thoroughly

### Phase 2: Make Event Mode Default
- Change default to `--mode event`
- Deprecate polling mode

### Phase 3: Remove Polling Mode
- Delete polling code path
- Simplify service

---

## 5. Configuration

Add to `llmc.toml`:

```toml
[daemon]
# Existing
nice_level = 19
pycache_cleanup_days = 7

# New
mode = "event"              # "event" | "poll" (legacy)
debounce_seconds = 2.0      # Wait after last change before processing
housekeeping_interval = 300 # Periodic wake for vacuum/log rotation (seconds)
```

---

## 6. Test Plan

### 6.1 Unit Tests
- [ ] `test_change_queue_debounce` - Verify debounce timing
- [ ] `test_change_queue_wait_blocks` - Verify wait() blocks when empty
- [ ] `test_repo_watcher_detects_changes` - Verify inotify events fire

### 6.2 Integration Tests
- [ ] `test_service_idles_at_zero_cpu` - Verify no CPU usage when idle
- [ ] `test_service_responds_to_file_change` - Verify processing starts after file save
- [ ] `test_service_handles_rapid_changes` - Verify debounce works with rapid edits

### 6.3 Manual Tests
- [ ] Start service, verify "Watching N repos" message
- [ ] Edit a file, verify processing starts within 3s
- [ ] Leave idle for 5 min, verify `top` shows 0% CPU

---

## 7. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| inotify watch limit | Check `fs.inotify.max_user_watches`, document how to increase |
| Missed events during high load | Inotify buffers events; debounce handles bursts |
| Non-Linux systems | Fall back to polling mode with warning |

---

## 8. Acceptance Criteria

- [ ] CPU usage < 1% when idle (currently 180%)
- [ ] File change → processing in < 3 seconds
- [ ] Existing `llmc-rag` commands unchanged
- [ ] All existing tests pass
- [ ] New tests for event-driven components

---

## 9. Implementation Checklist

- [ ] Create `tools/rag/watcher.py` with `RepoWatcher` and `ChangeQueue`
- [ ] Add `--mode` flag to service CLI
- [ ] Refactor `run_loop()` to support both modes
- [ ] Add configuration to `llmc.toml`
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Update CHANGELOG.md
- [ ] Manual testing
- [ ] PR review
