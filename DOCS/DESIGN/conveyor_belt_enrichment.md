# Conveyor Belt Enrichment Architecture

> **Design Document** | Created: 2025-12-24  
> **Status**: PROPOSAL (RFC)

## 1. Problem Statement

The current enrichment architecture has two modes:

1. **KISS Mode** (current baseline): Single async pipeline, sequential LLM calls
   - ✅ Zero lock contention  
   - ✅ Simple, reliable
   - ❌ ~70-80 T/s bottleneck (one backend at a time)

2. **Work-Stealing Pool** (deprecated): Multi-process workers + SQLite queue
   - ✅ ~210 T/s peak throughput
   - ❌ SQLite lock contention killed it
   - ❌ FIFO fragility, orphan recovery overhead

**Goal**: Achieve 200+ T/s without the operational complexity of multi-process SQLite coordination.

---

## 2. Conveyor Belt Pattern

Instead of distributed processes fighting over a SQLite queue, use **in-process async concurrency** with bounded semaphores.

### Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        SINGLE PROCESS                        │
│                                                              │
│  ┌──────────┐       ┌─────────────────┐       ┌───────────┐ │
│  │  FEEDER  │──────▶│   RAM QUEUE     │◀──────│  WRITERS  │ │
│  │ (SQLite) │       │  (asyncio.Queue)│       │  (SQLite) │ │
│  └──────────┘       └────────┬────────┘       └───────────┘ │
│                              │                              │
│              ┌───────────────┼───────────────┐              │
│              ▼               ▼               ▼              │
│      ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│      │   WORKER    │ │   WORKER    │ │   WORKER    │       │
│      │   @athena   │ │  @desktop   │ │  @localhost │       │
│      │ Semaphore=3 │ │ Semaphore=2 │ │ Semaphore=1 │       │
│      └─────────────┘ └─────────────┘ └─────────────┘       │
│              │               │               │              │
│              └───────────────┼───────────────┘              │
│                              ▼                              │
│                      ┌─────────────┐                        │
│                      │  COMPLETED  │                        │
│                      │   QUEUE     │                        │
│                      └─────────────┘                        │
└──────────────────────────────────────────────────────────────┘
```

### Key Components

#### 2.1 The Feeder (Producer)

```python
async def feeder(
    db: Database,
    work_queue: asyncio.Queue,
    batch_size: int = 50,
    refill_threshold: int = 10,
):
    """Prefetch spans into RAM queue.
    
    Uses SELECT ... FOR UPDATE SKIP LOCKED pattern (SQLite approximation).
    Wakes when queue is low, fills it back up, sleeps.
    """
    while True:
        if work_queue.qsize() < refill_threshold:
            # Fetch batch from DB - only hold lock briefly
            spans = db.pending_enrichments(limit=batch_size)
            for span in spans:
                await work_queue.put(span)
            
        await asyncio.sleep(0.5)  # Short poll interval
```

#### 2.2 Per-Backend Semaphores (Bounded Parallelism)

Each LLM server gets its own `BoundedSemaphore` that controls max concurrent requests:

```python
class BackendWorkerPool:
    """Manages parallel requests to a single LLM backend."""
    
    def __init__(self, backend: BackendAdapter, concurrency: int = 3):
        self.backend = backend
        self.semaphore = asyncio.BoundedSemaphore(concurrency)
        self.in_flight = 0
        
    async def process(self, span: SpanData) -> EnrichmentResult:
        """Process a span, respecting concurrency limit."""
        async with self.semaphore:
            self.in_flight += 1
            try:
                prompt = build_enrichment_prompt(span)
                result, meta = await asyncio.to_thread(
                    self.backend.generate, prompt, item=span.to_dict()
                )
                return EnrichmentResult(success=True, result=result, meta=meta)
            except BackendError as e:
                return EnrichmentResult(success=False, error=str(e))
            finally:
                self.in_flight -= 1
```

#### 2.3 Worker Coordinator (Consumer)

```python
class ConveyorBeltPipeline:
    """Orchestrates parallel enrichment with bounded semaphores."""
    
    def __init__(self, backends: list[BackendConfig], db: Database):
        self.db = db
        self.work_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.completed_queue: asyncio.Queue = asyncio.Queue()
        
        # Create worker pools with appropriate concurrency
        self.pools = []
        for cfg in backends:
            concurrency = self._compute_concurrency(cfg)
            adapter = create_backend_from_spec(cfg)
            pool = BackendWorkerPool(adapter, concurrency=concurrency)
            self.pools.append(pool)
    
    def _compute_concurrency(self, cfg: BackendConfig) -> int:
        """Determine max parallel requests per backend.
        
        Heuristics:
        - Local Ollama on GPU: 1-2 (GPU memory contention)
        - Remote Ollama: 2-4 (dedicated server)
        - Cloud API: 5-10 (designed for parallelism)
        """
        if cfg.provider in ("gemini", "openai", "anthropic", "groq"):
            return 10  # Cloud APIs handle parallelism well
        elif cfg.host != "localhost":
            return 3  # Remote Ollama server
        else:
            return 1  # Local GPU - avoid memory contention
    
    async def run(self, limit: int = 100, timeout: float = 300):
        """Run the conveyor belt until limit reached or timeout."""
        
        # Start feeder task
        feeder_task = asyncio.create_task(
            self._feeder_loop()
        )
        
        # Start writer task
        writer_task = asyncio.create_task(
            self._writer_loop()
        )
        
        # Start worker tasks for each pool
        worker_tasks = []
        for pool in self.pools:
            task = asyncio.create_task(
                self._worker_loop(pool)
            )
            worker_tasks.append(task)
        
        # Wait for limit or timeout
        await asyncio.wait_for(
            self._completion_monitor(limit),
            timeout=timeout
        )
        
        # Cleanup
        feeder_task.cancel()
        writer_task.cancel()
        for task in worker_tasks:
            task.cancel()
```

---

## 3. Configuration

```toml
[daemon.idle_enrichment]
enabled = true
batch_size = 50              # Items per feeder cycle
interval_seconds = 5

# NEW: Conveyor belt mode
[daemon.idle_enrichment.conveyor]
enabled = true               # Enable conveyor belt pattern
work_queue_size = 100        # RAM queue depth
refill_threshold = 20        # Refill when queue drops below this
total_workers = 10           # Total concurrent LLM requests across all backends

# Per-backend concurrency (overrides auto-detection)
[daemon.idle_enrichment.conveyor.concurrency]
athena = 4                   # Strix Halo can handle 4 parallel
desktop = 2                  # Desktop gets 2
localhost = 1                # Laptop iGPU gets 1
gemini = 10                  # Cloud API
```

---

## 4. Benefits Over Work-Stealing Pool

| Aspect | Work-Stealing Pool | Conveyor Belt |
|--------|-------------------|---------------|
| Processes | 3+ separate processes | Single process |
| IPC | SQLite queue + FIFO | `asyncio.Queue` (RAM) |
| Lock Contention | HIGH (SQLite WAL) | ZERO |
| Orphan Recovery | Required (stale claims) | Not needed |
| Debugging | Multi-process nightmare | Single async stack |
| Fault Isolation | Process crash = lost work | Exception = graceful |

---

## 5. Expected Performance

**Theoretical Max Throughput**:
- Athena (4 concurrent) × 60 T/s = 240 T/s
- Desktop (2 concurrent) × 50 T/s = 100 T/s  
- Localhost (1 concurrent) × 30 T/s = 30 T/s
- **Total: ~370 T/s** (if not IO-bound)

**Realistic Estimate**: 200-250 T/s (network latency, batch waits)

---

## 6. Implementation Plan

### Phase 1: Core Pipeline (Day 1)
- [ ] Create `llmc/rag/conveyor_pipeline.py`
- [ ] Implement `BackendWorkerPool` with `BoundedSemaphore`
- [ ] Implement async feeder/writer loops
- [ ] Add config parsing for `[daemon.idle_enrichment.conveyor]`

### Phase 2: Integration (Day 2)
- [ ] Modify `RAGService._run_idle_enrichment()` to use conveyor mode
- [ ] Add metrics collection (in-flight, completion rate, per-backend stats)
- [ ] Add graceful shutdown handling

### Phase 3: Validation (Day 3)
- [ ] Benchmark against KISS baseline
- [ ] Stress test with simulated backend failures
- [ ] Validate no SQLite lock issues under load

---

## 7. Alternative: Global Semaphore

Simpler approach if per-backend is overkill:

```python
# Single global semaphore for all LLM requests
global_semaphore = asyncio.BoundedSemaphore(10)

async def enrich_with_global_limit(span):
    async with global_semaphore:
        return await cascade.generate_for_span(span)
```

This loses per-backend fairness but is simpler to reason about.

---

## 8. Open Questions

1. **Backend Selection Strategy**: Round-robin vs weighted random vs fastest-first?
2. **Cascade in Parallel Mode**: If Athena fails, do we try Desktop immediately or queue for retry?
3. **Memory Pressure**: With 100 spans in RAM queue, memory footprint ~50MB. Acceptable?
4. **Backpressure**: If all backends are slow, feeder pauses. Need explicit backpressure signal?

---

## 9. References

- [Incident: 2025-12-23 Pool Stagnation](../../../.gemini/antigravity/knowledge/llmc_technical_implementation_and_security/artifacts/operational_incidents/2025-12-23_pool_stagnation_incident.md)
- Python `asyncio.BoundedSemaphore` docs
- SQLite WAL mode limitations
