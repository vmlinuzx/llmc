# Performance Audit Report: The Enrichment Loop (Conveyor Belt)
**Date:** 2025-12-24
**Auditor:** The Architect from Hell

## Executive Summary
The "Conveyor Belt" enrichment pipeline is a masterclass in unnecessary complexity masking fundamental performance anti-patterns. While it attempts to use `asyncio` for parallelism, it is bottlenecked by a complete lack of transactional awareness and a synchronous outer loop that prevents cross-repository scaling.

## Critical Findings

### 1. The "IOPS Killer" (Transactional Mismanagement)
In `llmc/rag/conveyor_pipeline.py`, the `_write_enrichment` method calls `self.db.conn.commit()` for **every single span**. 
- **Impact:** SQLite performance drops from thousands of inserts per second to dozens (depending on disk latency).
- **Remedy:** The `Writer` loop must use a transaction and commit in batches (e.g., every 50 items or every 5 seconds).

### 2. Synchronous Bottleneck (Cross-Repo Block)
`RAGService.run_loop_event` calls `asyncio.run(pipeline.run(...))` inside a sequential `for` loop over repositories.
- **Impact:** If Repo A is enriching a large batch, Repo B (which might have urgent file changes) is blocked until Repo A finishes.
- **Remedy:** The repository processing should be dispatched as independent async tasks or the `run_loop_event` should be fully async.

### 3. Hardcoded "Home Lab" Configuration
`ConveyorBeltPipeline.from_config` contains hardcoded hostnames like `"athena"` and `"desktop"` and hardcoded concurrency logic.
- **Impact:** The "Conveyor Belt" is effectively broken or sub-optimal on any machine not owned by the original developer.
- **Remedy:** Move concurrency and backend host capability logic to `llmc.toml`.

### 4. Primitive Async Patterns
The `Feeder` loop in the pipeline uses `await asyncio.sleep(0.5)` to poll the queue size.
- **Impact:** Unnecessary latency and CPU wakeups.
- **Remedy:** Use `asyncio.Queue` naturally; it handles backpressure without manual polling.

### 5. Intentional Locality Destruction
The `pending_enrichments` method shuffles spans "to avoid clustering."
- **Impact:** Increases random I/O and destroys potential benefits from file-system or database caching of related entities.
- **Remedy:** Remove the shuffle. Process files in order to maintain locality.

## Conclusion
"Engineering" says it's good. Engineering is hallucinating. This pipeline is a Rube Goldberg machine that manages to be both complex and slow. It needs immediate refactoring of its database interaction and service loop.
