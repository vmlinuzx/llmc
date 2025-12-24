# SDD: Event-Driven Enrichment Queue

**Status:** 🟡 Phases 0-4 Complete, Phase 5 Remaining  
**Author:** Dave + Antigravity  
**Created:** 2025-12-21  
**Updated:** 2025-12-23  
**Priority:** P1 (prerequisite for distributed enrichment)

## Implementation Status

| Phase | Description | Status | Files |
|-------|-------------|--------|-------|
| **Phase 0** | Central Work Queue | ✅ Complete | `llmc/rag/work_queue.py` (772 lines) |
| **Phase 1** | Indexer Integration | ✅ Complete | `feed_queue_from_repos()` in work_queue.py |
| **Phase 2** | Event Notification | ✅ Complete | Named pipe + `wait_for_work()` with select() |
| **Phase 3** | Worker Refactor | ✅ Complete | `llmc/rag/pool_worker.py` (582 lines) |
| **Phase 4** | Multi-Worker Support | ✅ Complete | `llmc/rag/pool_manager.py` (381 lines) |
| **Phase 5** | Remote Workers (HTTP API) | 🔴 Not Started | — |

### Known Issues (2025-12-23)

- **SQLite locking:** Multiple workers hitting `work_queue.db` simultaneously causes `database is locked` errors
- **FIFO pipe issues:** Named pipe creation/connection unreliable across daemon restarts
- **Workaround:** Currently using KISS mode (single-process async) as stable baseline

### Key Files

- `llmc/rag/work_queue.py` — Central queue: push/pull/complete/fail/heartbeat/orphan recovery
- `llmc/rag/pool_worker.py` — Backend-bound worker: pulls from queue, calls Ollama directly
- `llmc/rag/pool_manager.py` — Spawns/monitors multiple workers, scheduling, health checks
- `llmc/rag/pool_config.py` — Configuration for worker pool

## 1. Problem Statement

### Current State (Pain Points)

The enrichment daemon polls all registered repositories in a loop, even when most have zero pending work:

```python
while True:
    for repo in all_registered_repos:      # 20+ repos
        db = Database(repo / ".llmc/rag/rag.db")  # open each DB
        pending = db.pending_enrichments(limit=10)
        if not pending:
            continue  # wasted trip
        process(pending)
    time.sleep(60)  # arbitrary interval
```

**Problems:**
1. **O(repos) per iteration** - 19/20 repos have no work, still queried
2. **Dead repos accumulate** - moved/deleted repos stay in registry, spam errors
3. **No notification** - worker has no idea when work appears
4. **Idle CPU burn** - constant polling even when nothing to do
5. **Multi-worker impossible** - each worker would duplicate the repo scanning
6. **Latency** - new work waits up to 60s to be discovered

### Desired State

- **O(work)** - only touch repos/spans that have pending work
- **Event-driven** - worker sleeps until notified of new work
- **Central queue** - one source of truth for all pending enrichments
- **Multi-worker ready** - N workers pull from same queue
- **Zero idle CPU** - blocked on I/O, not spinning

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ENRICHMENT SYSTEM                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────┐     ┌──────────────┐     ┌─────────────────────────────┐  │
│  │ Indexer  │────▶│ Work Queue   │────▶│ Worker Pool                 │  │
│  │ (push)   │     │ (SQLite)     │     │ (pull, process, ack)        │  │
│  └──────────┘     └──────────────┘     └─────────────────────────────┘  │
│       │                  │                       │                       │
│       │                  │                       │                       │
│       ▼                  ▼                       ▼                       │
│  ┌──────────┐     ┌──────────────┐     ┌─────────────────────────────┐  │
│  │ inotify  │     │ Notification │     │ Ollama Backends             │  │
│  │ watcher  │     │ (pipe/event) │     │ (local + remote GPUs)       │  │
│  └──────────┘     └──────────────┘     └─────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key Components:**

1. **Work Queue** - Central SQLite table with all pending enrichment work
2. **Notification Channel** - Unix pipe or threading.Event for wake-up
3. **Worker Pool** - 1-N workers pulling from queue
4. **Push on Index** - Indexer notifies queue when spans created

---

## 3. Phases

### Phase 0: Foundation - Central Work Queue
**Difficulty:** 🟢 Easy (4-6 hours)  
**Risk:** Low

Create a global work queue table that aggregates pending work across all repos.

#### Steps

| Step | Description | Effort |
|------|-------------|--------|
| 0.1 | Create `~/.llmc/work_queue.db` with `pending_enrichments` table | 1h |
| 0.2 | Schema: `(id, repo_id, span_hash, file_path, priority, created_at, claimed_by, claimed_at)` | 30m |
| 0.3 | Add `push_work()` function - insert pending items | 1h |
| 0.4 | Add `pull_work(worker_id, limit)` - atomic claim with `claimed_by` | 1.5h |
| 0.5 | Add `complete_work(id)` and `fail_work(id, error)` | 1h |
| 0.6 | Add `orphan_recovery()` - reclaim work claimed >10min ago | 1h |

#### Schema

```sql
CREATE TABLE pending_enrichments (
    id INTEGER PRIMARY KEY,
    repo_path TEXT NOT NULL,          -- /home/dave/src/llmc
    span_hash TEXT NOT NULL,
    file_path TEXT NOT NULL,          -- relative to repo
    priority INTEGER DEFAULT 5,       -- 1=high, 10=low
    created_at REAL NOT NULL,         -- time.time()
    claimed_by TEXT,                  -- worker-id or NULL
    claimed_at REAL,
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    UNIQUE(repo_path, span_hash)
);

CREATE INDEX idx_pending_unclaimed ON pending_enrichments(claimed_by, priority, created_at)
    WHERE claimed_by IS NULL;
```

#### Success Criteria
- [ ] `push_work()` accepts repo + span_hash, inserts if not exists
- [ ] `pull_work()` returns N items atomically claimed by worker_id
- [ ] `complete_work()` deletes item from queue
- [ ] `fail_work()` increments attempts, clears claimed_by for retry
- [ ] Orphan recovery runs every 5 minutes, reclaims stale claims

---

### Phase 1: Indexer Integration - Push on Create
**Difficulty:** 🟢 Easy (2-3 hours)  
**Risk:** Low

Modify the indexer to push new spans to the central queue.

#### Steps

| Step | Description | Effort |
|------|-------------|--------|
| 1.1 | Add `WorkQueue` class to `llmc/rag/work_queue.py` | 30m |
| 1.2 | In `indexer.py:replace_spans()`, call `queue.push_work()` for new spans | 1h |
| 1.3 | Add priority calculation (code > docs, recent > old) | 30m |
| 1.4 | Add `--no-queue` flag for indexer (testing/migration) | 30m |
| 1.5 | Backfill script: scan all repos, push existing pending work to queue | 30m |

#### Integration Point

```python
# In indexer.py:replace_spans()
def replace_spans(self, file_id: int, spans: Sequence[SpanRecord]) -> None:
    # ... existing differential logic ...
    
    # NEW: Push new spans to central queue
    if to_add:
        from llmc.rag.work_queue import get_queue
        queue = get_queue()
        for span in new_spans:
            queue.push_work(
                repo_path=str(self.repo_root),
                span_hash=span.span_hash,
                file_path=str(span.file_path),
                priority=self._calculate_priority(span)
            )
```

#### Success Criteria
- [ ] New spans appear in central queue within 1s of indexing
- [ ] Re-indexing same file doesn't duplicate queue entries (UNIQUE constraint)
- [ ] Backfill script populates queue for existing repos
- [ ] Queue visible via `llmc debug queue stats`

---

### Phase 2: Event Notification - Wake on Work
**Difficulty:** 🟡 Medium (3-4 hours)  
**Risk:** Medium (cross-process signaling)

Add notification mechanism so workers wake immediately when work is pushed.

#### Steps

| Step | Description | Effort |
|------|-------------|--------|
| 2.1 | Create `/run/llmc/` directory on daemon start | 15m |
| 2.2 | Create named pipe `/run/llmc/work-notify` | 30m |
| 2.3 | In `push_work()`, write 1 byte to pipe after insert | 30m |
| 2.4 | In worker, `select()` on pipe with timeout for housekeeping | 1.5h |
| 2.5 | Handle pipe reconnection (daemon restart scenarios) | 1h |
| 2.6 | Fallback to polling if pipe unavailable (graceful degradation) | 30m |

#### Notification Pattern

```python
# In work_queue.py
class WorkQueue:
    def __init__(self):
        self._notify_pipe = self._open_notify_pipe()
    
    def push_work(self, ...):
        # Insert into DB
        self._db.execute("INSERT INTO pending_enrichments ...")
        
        # Wake any sleeping workers
        if self._notify_pipe:
            try:
                os.write(self._notify_pipe, b"w")  # "work available"
            except BrokenPipeError:
                pass  # No workers listening, that's fine

# In worker
def run_worker():
    queue = WorkQueue()
    notify_fd = os.open("/run/llmc/work-notify", os.O_RDONLY | os.O_NONBLOCK)
    
    while True:
        # Block until notified OR timeout (for housekeeping)
        readable, _, _ = select.select([notify_fd], [], [], timeout=300)
        
        if readable:
            os.read(notify_fd, 1024)  # Drain pipe
        
        # Process available work
        items = queue.pull_work(worker_id=WORKER_ID, limit=10)
        for item in items:
            process_enrichment(item)
            queue.complete_work(item.id)
```

#### Success Criteria
- [ ] Worker CPU at ~0% when queue empty
- [ ] Worker wakes within 100ms of new work being pushed
- [ ] Multiple workers all wake on notification (broadcast)
- [ ] Daemon restart doesn't break workers (pipe recreation)
- [ ] Falls back to 60s polling if pipe fails

---

### Phase 3: Worker Refactor - Queue Consumers
**Difficulty:** 🟡 Medium (4-6 hours)  
**Risk:** Medium (rip out existing loop)

Replace the repo-polling worker with queue-pulling workers.

#### Steps

| Step | Description | Effort |
|------|-------------|--------|
| 3.1 | Create `llmc/rag/enrichment_worker.py` (new clean implementation) | 2h |
| 3.2 | Worker pulls from queue, opens repo DB only when processing | 1h |
| 3.3 | Worker reports metrics: items/sec, idle time, GPU utilization | 1h |
| 3.4 | Add `llmc service worker start` command | 30m |
| 3.5 | Add worker health endpoint (`/health` for monitoring) | 30m |
| 3.6 | Deprecate old `execute_enrichment` loop (keep for 1 release) | 30m |
| 3.7 | Update systemd service to use new worker | 30m |

#### New Worker Structure

```python
# llmc/rag/enrichment_worker.py

class EnrichmentWorker:
    def __init__(self, worker_id: str, ollama_host: str = "localhost:11434"):
        self.worker_id = worker_id
        self.queue = WorkQueue()
        self.ollama = OllamaBackend(host=ollama_host)
        self.stats = WorkerStats()
    
    def run(self):
        log.info(f"Worker {self.worker_id} started")
        
        while True:
            self.wait_for_work()  # Blocks on notification pipe
            
            items = self.queue.pull_work(self.worker_id, limit=10)
            if not items:
                continue
            
            for item in items:
                try:
                    self.process(item)
                    self.queue.complete_work(item.id)
                    self.stats.record_success()
                except Exception as e:
                    self.queue.fail_work(item.id, str(e))
                    self.stats.record_failure()
    
    def process(self, item: WorkItem):
        # Open repo DB only when needed
        db = Database(Path(item.repo_path) / ".llmc/rag/rag.db")
        span = db.get_span_by_hash(item.span_hash)
        
        # ... existing enrichment logic ...
```

#### Success Criteria
- [ ] New worker processes enrichments correctly (output matches old worker)
- [ ] Worker opens repo DB only for items it's processing
- [ ] Worker stats visible via `llmc debug worker stats`
- [ ] Systemd service starts new worker without issues
- [ ] Old worker deprecated but still functional for rollback

---

### Phase 4: Multi-Worker Support
**Difficulty:** 🟢 Easy (2-3 hours)  
**Risk:** Low (queue already handles concurrency)

Enable running multiple workers on same host.

#### Steps

| Step | Description | Effort |
|------|-------------|--------|
| 4.1 | Add `--workers N` flag to `llmc service start` | 30m |
| 4.2 | Spawn N worker processes with unique IDs | 30m |
| 4.3 | Add worker coordination (graceful shutdown, health checks) | 1h |
| 4.4 | Per-worker GPU assignment via `CUDA_VISIBLE_DEVICES` | 30m |
| 4.5 | Aggregate stats across workers | 30m |

#### Configuration

```toml
# llmc.toml
[enrichment.workers]
count = 3                          # Number of local workers
gpu_assignment = "round-robin"     # or "manual" with per-worker GPU IDs

[[enrichment.workers.instances]]
id = "worker-0"
gpu = 0
ollama_host = "localhost:11434"

[[enrichment.workers.instances]]  
id = "worker-1"
gpu = 1
ollama_host = "localhost:11435"
```

#### Success Criteria
- [ ] `llmc service start --workers 3` spawns 3 worker processes
- [ ] Each worker processes different queue items (no duplicates)
- [ ] Workers gracefully shutdown on SIGTERM
- [ ] Aggregate throughput ~= N × single worker throughput
- [ ] `llmc debug worker stats` shows all workers

---

### Phase 5: Remote Workers (Distributed)
**Difficulty:** 🟡 Medium (6-8 hours)  
**Risk:** Medium (network, auth, failure handling)

Enable workers on remote hosts (kids' machines, Strix Halo, etc.)

#### Steps

| Step | Description | Effort |
|------|-------------|--------|
| 5.1 | Add HTTP API for queue operations (`/queue/pull`, `/queue/complete`) | 2h |
| 5.2 | Add authentication (API key in header) | 1h |
| 5.3 | Remote worker: pulls via HTTP instead of direct SQLite | 1.5h |
| 5.4 | Handle network failures (retry with backoff) | 1h |
| 5.5 | Add `llmc service remote-worker` command | 30m |
| 5.6 | Dashboard: show remote worker status | 1h |
| 5.7 | Documentation: setup guide for remote workers | 1h |

#### Remote Worker Flow

```
┌─────────────────────┐         HTTP          ┌─────────────────────┐
│ Central Queue       │◀────────────────────▶│ Remote Worker       │
│ (host: llmc-server) │  GET /queue/pull     │ (host: kids-pc)     │
│                     │  POST /queue/complete │                     │
└─────────────────────┘                       └─────────────────────┘
                                                       │
                                                       ▼
                                              ┌─────────────────────┐
                                              │ Local Ollama        │
                                              │ (RTX 2060)          │
                                              └─────────────────────┘
```

#### Success Criteria
- [ ] Remote worker connects to queue server via HTTP
- [ ] Authentication prevents unauthorized access
- [ ] Network failure doesn't lose work (retry + orphan recovery)
- [ ] Remote worker throughput comparable to local worker
- [ ] Dashboard shows remote workers with latency metrics

---

## 4. User Acceptance Testing (UAT)

### UAT-1: Zero Idle CPU
**Scenario:** Queue is empty, worker running.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Start worker with empty queue | Worker blocks on notification |
| 2 | Monitor CPU for 5 minutes | CPU usage < 1% |
| 3 | Push 1 item to queue | Worker wakes within 1 second |
| 4 | Item processed, queue empty | Worker returns to blocking |

### UAT-2: Instant Wake on Work
**Scenario:** New file indexed, enrichment should start immediately.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Worker running, queue empty | Worker blocked |
| 2 | Create new Python file in repo | inotify detects change |
| 3 | Indexer runs, creates spans | Spans pushed to queue |
| 4 | Measure time to enrichment start | < 3 seconds end-to-end |

### UAT-3: Multi-Worker Throughput
**Scenario:** 3 workers should process ~3x as fast.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Queue 100 items (synthetic) | Items visible in queue stats |
| 2 | Run 1 worker, measure time to empty | T1 = X seconds |
| 3 | Queue 100 items again | Queue refilled |
| 4 | Run 3 workers, measure time to empty | T3 ≈ T1/3 (within 20%) |
| 5 | Verify no duplicate processing | Each item processed exactly once |

### UAT-4: Dead Repo Handling
**Scenario:** Repo deleted, queue should not accumulate errors.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Register repo, index, push work | Queue contains items |
| 2 | Delete repo directory | Repo gone from filesystem |
| 3 | Worker attempts to process | Fails with "repo not found" |
| 4 | Item marked failed after 3 attempts | Item removed from active queue |
| 5 | Worker continues with other items | No infinite retry loop |

### UAT-5: Remote Worker
**Scenario:** Worker on different machine processes work.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Start queue server on host A | HTTP API available |
| 2 | Start remote worker on host B | Worker connects to A |
| 3 | Push work to queue | Worker B pulls and processes |
| 4 | Verify enrichment stored in repo DB | Enrichment visible via mcgrep |
| 5 | Kill network between A and B | Worker B retries with backoff |
| 6 | Restore network | Worker B reconnects, resumes |

---

## 5. What Success Looks Like

### Before (Current State)
```
$ htop
  PID  CPU%  Command
12345  15%   python3 llmc-rag-service  # constant polling
...

$ llmc debug doctor
Enrichment service: running (checked 23 repos, 0 pending)
Time since last work: 4 hours
Repos with errors: 5 (paths not found)
```

### After (Success State)
```
$ htop
  PID  CPU%  Command
12345   0%   python3 llmc-worker-0  # blocked on pipe
12346   0%   python3 llmc-worker-1  # blocked on pipe
12347  45%   python3 llmc-worker-2  # actively processing
...

$ llmc debug queue stats
Central Queue: 47 pending, 0 in-progress, 1203 completed today
Workers: 3 local, 2 remote
  worker-0 (local, GPU:0): idle, 412 today @ 78 T/s avg
  worker-1 (local, GPU:1): idle, 398 today @ 75 T/s avg
  worker-2 (local, GPU:2): processing span abc123, 405 today @ 76 T/s avg
  worker-athena (remote): processing span def456, 892 today @ 82 T/s avg
  worker-kids-pc (remote): idle, 156 today @ 45 T/s avg

Aggregate throughput: 2263 enrichments/day @ 71 T/s avg
Queue latency: 1.2s (push to process start)
Dead repos auto-removed: 3 this week
```

### Key Metrics

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Idle CPU usage | 15% | < 1% | 15x reduction |
| Work discovery latency | 60s avg | < 2s | 30x faster |
| Throughput (3 GPUs) | 80 T/s (1 GPU) | 240 T/s | 3x |
| Dead repo errors | 5/day | 0 (auto-cleanup) | Eliminated |
| Code complexity | O(repos × polls) | O(work) | Architectural |

---

## 6. Migration Plan

### Week 1: Phase 0 + 1
- Create central queue table
- Integrate with indexer (push on create)
- Backfill existing pending work
- **Milestone:** Queue populated, visible via `llmc debug queue stats`

### Week 2: Phase 2 + 3
- Add notification pipe
- Implement new worker
- Run new worker alongside old (shadow mode)
- **Milestone:** New worker processing correctly, CPU near zero when idle

### Week 3: Phase 4
- Multi-worker on same host
- GPU assignment
- Deprecate old enrichment loop
- **Milestone:** 3 local workers running, ~3x throughput

### Week 4+: Phase 5 (Optional)
- HTTP queue API
- Remote workers
- Dashboard
- **Milestone:** Kids' PC contributing to enrichment

---

## 7. Rollback Plan

Each phase is independently rollbackable:

| Phase | Rollback Action |
|-------|-----------------|
| 0 | Delete `work_queue.db`, no other changes |
| 1 | Revert indexer changes, queue stops filling |
| 2 | Workers fall back to polling (graceful degradation) |
| 3 | Switch systemd back to old service file |
| 4 | Run with `--workers 1` |
| 5 | Disable HTTP API, remote workers disconnect |

---

## 8. Future Considerations

- **Priority queues:** Separate queues for code vs docs, user-triggered vs background
- **Rate limiting:** Per-repo throttling to prevent one repo starving others
- **Cost tracking:** For cloud enrichment fallback (DeepSeek API)
- **Queue persistence:** WAL mode, crash recovery guarantees
- **Metrics export:** Prometheus endpoint for Grafana dashboards

---

## Appendix A: Alternatives Considered

### Redis Queue
**Pros:** Battle-tested, pub/sub built-in, clustering  
**Cons:** External dependency, overkill for local use  
**Decision:** SQLite is already a dependency, simpler stack

### PostgreSQL LISTEN/NOTIFY
**Pros:** Built-in pub/sub, ACID  
**Cons:** Heavy dependency for simple use case  
**Decision:** Named pipe achieves same result with zero deps

### In-Memory Queue (multiprocessing.Queue)
**Pros:** No disk I/O, very fast  
**Cons:** Lost on crash, can't span hosts  
**Decision:** SQLite provides durability, HTTP spans hosts

---

## Appendix B: Reference Implementation

See prototype branch: `feature/enrichment-queue` (to be created)

Key files:
- `llmc/rag/work_queue.py` - Queue operations
- `llmc/rag/enrichment_worker.py` - New worker implementation
- `llmc/rag/queue_api.py` - HTTP API for remote workers (Phase 5)
