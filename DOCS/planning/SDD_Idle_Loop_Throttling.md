# SDD: Idle Loop Throttling (Roadmap 1.6)

**Author:** Otto (Claude Opus 4.5)  
**Date:** 2025-12-02  
**Status:** Ready to Implement  
**Effort:** 2-3 hours  
**Difficulty:** 🟢 Easy

---

## Problem

The RAG service daemon burns CPU even when idle:

```
while self.running:
    for repo in repos:
        self.process_repo(repo)      # Always runs, even if no changes
    time.sleep(interval)             # Fixed 180s, no backoff
```

**Symptoms:**
- P16 fan spinning with no actual work queued
- Constant subprocess spawns to check for changes
- No distinction between "busy" and "idle" states
- Process runs at normal priority, competing with your actual work

---

## Solution

Three simple changes:

### 1. Set Process Nice Level (+10)

Run the daemon at lower priority so it doesn't compete with interactive work.

```python
import os

def run_loop(self, interval: int):
    # Set nice level at startup (lower priority)
    try:
        os.nice(10)  # +10 = lower priority (range: -20 to +19)
    except OSError:
        pass  # Ignore if we can't nice (containerized, etc.)
```

### 2. Track Idle Cycles

Detect when a cycle did no meaningful work:

```python
def process_repo(self, repo_path: str) -> bool:
    """Process one repo. Returns True if work was done."""
    # ... existing code ...
    
    changes = detect_changes(repo, index_path=index_path)
    if not changes:
        # No file changes, check if enrichment/embedding needed
        pending_enrich = get_pending_enrichment_count(repo)
        pending_embed = get_pending_embedding_count(repo)
        
        if pending_enrich == 0 and pending_embed == 0:
            print(f"  ℹ️  {repo.name}: Nothing to do")
            return False  # No work done
    
    # ... rest of processing ...
    return True  # Work was done
```

### 3. Exponential Backoff When Idle

Lengthen sleep time when consecutive cycles find no work:

```python
def run_loop(self, interval: int):
    idle_cycles = 0
    max_idle_multiplier = 10  # Cap at 10x interval (30 min if interval=180s)
    
    while self.running:
        work_done = False
        
        for repo in self.state.state["repos"]:
            if self.process_repo(repo):
                work_done = True
        
        if work_done:
            idle_cycles = 0  # Reset on any work
        else:
            idle_cycles += 1
        
        # Calculate sleep with backoff
        multiplier = min(2 ** idle_cycles, max_idle_multiplier)
        sleep_time = interval * multiplier
        
        if idle_cycles > 0:
            print(f"💤 Idle x{idle_cycles}, sleeping {int(sleep_time)}s...")
        else:
            print(f"💤 Sleeping {int(sleep_time)}s...")
        
        # Sleep in chunks so we can respond to signals
        self._interruptible_sleep(sleep_time)
```

### 4. Interruptible Sleep

Sleep in small chunks so SIGTERM is handled promptly:

```python
def _interruptible_sleep(self, seconds: float):
    """Sleep in 5s chunks so signals are handled promptly."""
    chunk = 5.0
    remaining = seconds
    while remaining > 0 and self.running:
        time.sleep(min(chunk, remaining))
        remaining -= chunk
```

---

## Configuration

Add to `llmc.toml`:

```toml
[daemon]
nice_level = 10                    # Process priority (0-19, higher = lower priority)
idle_backoff_max = 10              # Max multiplier when idle (10x = 30min at default)
idle_backoff_base = 2              # Exponential base (2^n)
```

---

## Implementation

### Files to Modify

```
tools/rag/service.py
├── RAGService.__init__()         # Load daemon config
├── RAGService.run_loop()         # Add nice level, backoff logic
├── RAGService.process_repo()     # Return bool for work done
└── RAGService._interruptible_sleep()  # New helper
```

### Code Changes

**1. Add nice level at daemon start:**
```python
def run_loop(self, interval: int):
    """Main service loop."""
    # Set low priority
    nice_level = self._daemon_cfg.get("nice_level", 10)
    try:
        current = os.nice(0)
        os.nice(nice_level - current)  # Adjust relative to current
        print(f"   Nice level: +{nice_level}")
    except OSError as e:
        print(f"   ⚠️  Could not set nice level: {e}")
    
    # ... rest of existing setup ...
```

**2. Track work in process_repo:**
```python
def process_repo(self, repo_path: str) -> bool:
    """Process one repo. Returns True if any work was done."""
    repo = Path(repo_path)
    if not repo.exists():
        print(f"⚠️  Repo not found: {repo_path}")
        return False

    work_done = False
    
    # Step 1: Detect changes
    changes = detect_changes(repo, index_path=index_path)
    if changes:
        run_sync(repo, changes)
        print(f"  ✅ Synced {len(changes)} changed files")
        work_done = True
    
    # Step 2: Enrich (only if pending)
    pending = get_pending_enrichment_count(repo)  # Need to add this helper
    if pending > 0:
        run_enrich(repo, ...)
        work_done = True
    
    # ... similar for embed ...
    
    return work_done
```

**3. Backoff loop:**
```python
def run_loop(self, interval: int):
    idle_cycles = 0
    max_mult = self._daemon_cfg.get("idle_backoff_max", 10)
    base = self._daemon_cfg.get("idle_backoff_base", 2)
    
    while self.running:
        cycle_start = time.time()
        work_done = False
        
        for repo in self.state.state["repos"]:
            if not self.running:
                break
            if self.process_repo(repo):
                work_done = True
        
        # Backoff logic
        if work_done:
            idle_cycles = 0
        else:
            idle_cycles += 1
        
        multiplier = min(base ** idle_cycles, max_mult)
        target_sleep = interval * multiplier
        
        elapsed = time.time() - cycle_start
        sleep_time = max(0, target_sleep - elapsed)
        
        if sleep_time > 0 and self.running:
            if idle_cycles > 0:
                print(f"💤 Idle x{idle_cycles} → sleeping {int(sleep_time)}s")
            else:
                print(f"💤 Sleeping {int(sleep_time)}s")
            self._interruptible_sleep(sleep_time)
    
    self.state.set_stopped()
```

---

## Behavior Examples

### Scenario 1: Active Development
```
Cycle 1: 5 files changed → work done → sleep 180s
Cycle 2: 2 files changed → work done → sleep 180s
Cycle 3: 0 changes, 10 pending enrich → work done → sleep 180s
```

### Scenario 2: Idle Repo
```
Cycle 1: 0 changes, 0 pending → idle x1 → sleep 360s (2x)
Cycle 2: 0 changes, 0 pending → idle x2 → sleep 720s (4x)
Cycle 3: 0 changes, 0 pending → idle x3 → sleep 1440s (8x)
Cycle 4: 0 changes, 0 pending → idle x4 → sleep 1800s (10x cap = 30min)
Cycle 5: 1 file changed → work done → reset → sleep 180s
```

### Scenario 3: CPU Impact
```
Before: 180s cycles = 480 cycles/day = constant subprocess churn
After:  With backoff, idle repos: ~50 cycles/day (90% reduction)
        + nice +10 = doesn't compete with your IDE/browser
```

---

## Testing

### Manual Test
```bash
# Start daemon
llmc-rag start

# Watch it back off when idle
llmc-rag logs -f

# Should see:
#   💤 Idle x1 → sleeping 360s
#   💤 Idle x2 → sleeping 720s
#   ...

# Touch a file in registered repo
touch /path/to/repo/foo.py

# Should see on next cycle:
#   ✅ Synced 1 changed files
#   💤 Sleeping 180s (reset)
```

### Verify Nice Level
```bash
# Find the daemon PID
llmc-rag status

# Check nice level
ps -o pid,ni,comm -p <PID>
# Should show NI = 10
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Miss urgent changes during long sleep | Interruptible sleep checks `self.running` every 5s; can also add file watcher trigger (P2) |
| Nice level not settable (container) | Catch OSError, log warning, continue |
| Backoff too aggressive | Cap at 10x (configurable), instant reset on any work |

---

## Future Enhancements (P2)

1. **inotify/fswatch trigger:** Wake immediately on file changes instead of waiting for next poll
2. **Per-repo idle tracking:** Repos with different activity levels get different backoff
3. **ionice:** Also set I/O priority for database operations

---

## Summary

| Change | Impact |
|--------|--------|
| `os.nice(10)` | Won't steal CPU from your actual work |
| Work detection | Know when to back off |
| Exponential backoff | 90% fewer cycles when idle |
| Interruptible sleep | Still responds to signals |

**Total effort: ~2-3 hours** to implement and test.
