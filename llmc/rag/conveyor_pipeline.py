"""
Conveyor Belt Enrichment Pipeline - Bounded Semaphore Pattern

Single-process async pipeline that enables parallel LLM requests without
SQLite lock contention. Uses asyncio.BoundedSemaphore to control concurrency
per backend server.

Key insight: No multi-process coordination needed. SQLite is only touched by
the Feeder (reads) and Writer (writes) - never concurrently.

Usage:
    from llmc.rag.conveyor_pipeline import ConveyorBeltPipeline
    
    async def main():
        pipeline = ConveyorBeltPipeline.from_config(repo_root)
        result = await pipeline.run(limit=100)
        print(f"Enriched {result.succeeded} spans at {result.throughput:.1f} T/s")
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

from llmc.rag.config_enrichment import EnrichmentBackendSpec
from llmc.rag.enrichment_backends import BackendAdapter, BackendError
from llmc.rag.enrichment_pipeline import build_enrichment_prompt
from llmc.rag.enrichment_router import EnrichmentSliceView

if TYPE_CHECKING:
    from llmc.rag.database import Database


@dataclass
class BackendWorkerConfig:
    """Configuration for a single backend worker."""
    name: str
    spec: EnrichmentBackendSpec
    concurrency: int = 2  # Max parallel requests to this backend


@dataclass
class ConveyorConfig:
    """Configuration for the conveyor belt pipeline."""
    backends: list[BackendWorkerConfig]
    work_queue_size: int = 100
    refill_threshold: int = 20
    batch_size: int = 50


@dataclass
class ConveyorResult:
    """Result of a conveyor belt run."""
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    duration_sec: float = 0.0
    per_backend_stats: dict[str, dict[str, int]] = field(default_factory=dict)
    
    @property
    def throughput(self) -> float:
        """Tokens per second (estimated)."""
        if self.duration_sec == 0:
            return 0.0
        # Rough estimate: 350 tokens per span
        return (self.succeeded * 350) / self.duration_sec


@dataclass
class WorkItem:
    """A span ready for enrichment."""
    slice_view: EnrichmentSliceView
    prompt: str
    item_dict: dict[str, Any]
    attempt: int = 0


class BackendWorkerPool:
    """Manages parallel requests to a single LLM backend.
    
    Uses asyncio.BoundedSemaphore to limit concurrent requests.
    The semaphore ensures we never exceed the backend's capacity.
    """
    
    def __init__(
        self,
        backend: BackendAdapter,
        name: str,
        concurrency: int = 2,
    ):
        self.backend = backend
        self.name = name
        self.concurrency = concurrency
        self.semaphore = asyncio.BoundedSemaphore(concurrency)
        
        # Stats
        self.in_flight = 0
        self.completed = 0
        self.failed = 0
        
    async def process(self, work: WorkItem) -> tuple[bool, dict[str, Any] | None, dict[str, Any] | None, str | None]:
        """Process a work item through this backend.
        
        Returns:
            (success, result_dict, meta_dict, error_message)
        """
        async with self.semaphore:
            self.in_flight += 1
            try:
                # Run the synchronous backend.generate in a thread pool
                # This prevents blocking the event loop
                result, meta = await asyncio.to_thread(
                    self.backend.generate,
                    work.prompt,
                    item=work.item_dict,
                )
                self.completed += 1
                return True, result, meta, None
                
            except BackendError as e:
                self.failed += 1
                return False, None, None, str(e)
                
            except Exception as e:
                self.failed += 1
                return False, None, None, f"Unexpected: {e}"
                
            finally:
                self.in_flight -= 1
    
    def stats(self) -> dict[str, int]:
        return {
            "in_flight": self.in_flight,
            "completed": self.completed,
            "failed": self.failed,
        }


class ConveyorBeltPipeline:
    """Single-process async pipeline for parallel enrichment.
    
    Architecture:
    - Feeder: Pulls spans from SQLite, puts into RAM queue
    - Workers: Per-backend async tasks with bounded semaphores
    - Writer: Takes completed items, writes to SQLite
    
    SQLite is only touched by Feeder and Writer, never concurrently.
    """
    
    def __init__(
        self,
        db: Database,
        backend_factory: callable,
        config: ConveyorConfig,
        *,
        repo_root: Path | None = None,
    ):
        self.db = db
        self.backend_factory = backend_factory
        self.config = config
        self.repo_root = repo_root or db.repo_root
        
        # Queues
        self.work_queue: asyncio.Queue[WorkItem | None] = asyncio.Queue(
            maxsize=config.work_queue_size
        )
        self.completed_queue: asyncio.Queue[tuple[WorkItem, bool, dict | None, dict | None]] = asyncio.Queue()
        
        # Create worker pools
        self.pools: list[BackendWorkerPool] = []
        for backend_cfg in config.backends:
            adapter = backend_factory(backend_cfg.spec)
            pool = BackendWorkerPool(
                backend=adapter,
                name=backend_cfg.name,
                concurrency=backend_cfg.concurrency,
            )
            self.pools.append(pool)
        
        # State
        self._running = False
        self._items_fed = 0
        self._items_completed = 0
        self._target_limit = 0
    
    @classmethod
    def from_config(cls, repo_root: Path) -> ConveyorBeltPipeline:
        """Create pipeline from llmc.toml configuration."""
        from llmc.rag.config import index_path_for_write, load_config
        from llmc.rag.database import Database
        from llmc.rag.enrichment_factory import create_backend_from_spec
        
        # Load config
        cfg = load_config(repo_root)
        
        # Build backend configs from enrichment chains
        conveyor_cfg = cfg.get("daemon", {}).get("idle_enrichment", {}).get("conveyor", {})
        concurrency_overrides = conveyor_cfg.get("concurrency", {})
        
        # Get enabled enrichment chains
        chains = cfg.get("enrichment", {}).get("chain", [])
        if isinstance(chains, dict):
            chains = [chains]
        
        backends = []
        
        # Determine which tiers to process in parallel
        # Default to fast local tiers, but allow config to override
        target_tiers = set(conveyor_cfg.get("tiers", ["4b", "nano", "7b", "8b"]))
        
        for chain in chains:
            if not chain.get("enabled", True):
                continue
            
            # Use routing_tier to decide if this belongs in the conveyor
            tier = chain.get("routing_tier", "")
            if tier and tier not in target_tiers:
                continue
            
            # Skip providers that don't support async/parallel well or have auth issues in daemon
            provider = chain.get("provider", "ollama")
            if provider in ("gemini", "anthropic", "groq", "minimax"):
                # These often have rate limits or env var issues in systemd
                continue
            
            name = chain.get("name", "unknown")
            
            # Determine concurrency:
            # 1. Check overrides by name
            # 2. Check overrides by host/url
            # 3. Default to 2
            concurrency = concurrency_overrides.get(name)
            if concurrency is None:
                url = chain.get("url", "")
                for key, val in concurrency_overrides.items():
                    if key in url:
                        concurrency = val
                        break
            
            if concurrency is None:
                concurrency = 2 # Reasonable default for modern GPUs
            
            spec = EnrichmentBackendSpec(
                name=name,
                provider=provider,
                model=chain.get("model", ""),
                url=chain.get("url"),
                timeout_seconds=chain.get("timeout_seconds", 90),
                options=chain.get("options", {}),
            )
            
            backends.append(BackendWorkerConfig(
                name=name,
                spec=spec,
                concurrency=int(concurrency),
            ))
        
        config = ConveyorConfig(
            backends=backends,
            work_queue_size=conveyor_cfg.get("work_queue_size", 100),
            refill_threshold=conveyor_cfg.get("refill_threshold", 20),
            batch_size=conveyor_cfg.get("batch_size", 50),
        )
        
        # Create database
        index_path = index_path_for_write(repo_root)
        db = Database(index_path)
        
        return cls(
            db=db,
            backend_factory=create_backend_from_spec,
            config=config,
            repo_root=repo_root,
        )
    
    async def run(self, limit: int = 100, timeout: float = 300.0) -> ConveyorResult:
        """Run the conveyor belt pipeline.
        
        Args:
            limit: Maximum spans to process
            timeout: Maximum runtime in seconds
            
        Returns:
            ConveyorResult with stats
        """
        self._running = True
        self._target_limit = limit
        self._items_fed = 0
        self._items_completed = 0
        
        start_time = time.monotonic()
        
        try:
            # Start all tasks
            feeder_task = asyncio.create_task(self._feeder_loop())
            writer_task = asyncio.create_task(self._writer_loop())
            
            worker_tasks = []
            for pool in self.pools:
                task = asyncio.create_task(self._worker_loop(pool))
                worker_tasks.append(task)
            
            # Wait for completion or timeout
            try:
                await asyncio.wait_for(
                    self._wait_for_completion(),
                    timeout=timeout,
                )
            except TimeoutError:
                print(f"⏱️ Conveyor belt timed out after {timeout}s")
            
        finally:
            self._running = False
            
            # Signal workers to stop
            for _ in self.pools:
                await self.work_queue.put(None)
            
            # Cancel tasks
            feeder_task.cancel()
            writer_task.cancel()
            for task in worker_tasks:
                task.cancel()
            
            # Wait for cleanup
            await asyncio.sleep(0.1)
        
        duration = time.monotonic() - start_time
        
        # Collect stats
        succeeded = sum(p.completed for p in self.pools)
        failed = sum(p.failed for p in self.pools)
        
        return ConveyorResult(
            attempted=succeeded + failed,
            succeeded=succeeded,
            failed=failed,
            duration_sec=duration,
            per_backend_stats={p.name: p.stats() for p in self.pools},
        )
    
    async def _feeder_loop(self):
        """Feed work items into the queue from the database."""
        while self._running:
            # Check if we need to refill
            if self.work_queue.qsize() >= self.config.refill_threshold:
                await asyncio.sleep(0.5)
                continue
            
            # Check if we've fed enough
            if self._items_fed >= self._target_limit:
                await asyncio.sleep(0.5)
                continue
            
            # Fetch batch from database
            remaining = self._target_limit - self._items_fed
            batch_size = min(self.config.batch_size, remaining)
            
            try:
                # This is sync SQLite access - fine since we're the only reader
                spans = self._get_pending_spans(batch_size)
                
                for span_data in spans:
                    if not self._running:
                        break
                    
                    # Build work item
                    work = self._create_work_item(span_data)
                    if work:
                        await self.work_queue.put(work)
                        self._items_fed += 1
                        
            except Exception as e:
                print(f"❌ Feeder error: {e}")
                await asyncio.sleep(1.0)
    
    async def _worker_loop(self, pool: BackendWorkerPool):
        """Worker loop for a single backend pool."""
        while self._running:
            try:
                # Get work with timeout so we can check _running
                try:
                    work = await asyncio.wait_for(
                        self.work_queue.get(),
                        timeout=1.0,
                    )
                except TimeoutError:
                    continue
                
                if work is None:  # Shutdown signal
                    break
                
                # Process through this backend
                success, result, meta, error = await pool.process(work)
                
                # Queue for writing
                await self.completed_queue.put((work, success, result, meta))
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Worker {pool.name} error: {e}")
    
    async def _writer_loop(self):
        """Write completed enrichments to database."""
        pending_count = 0
        last_commit = time.time()
        commit_interval = 5.0  # seconds
        commit_threshold = 50  # items

        while self._running or not self.completed_queue.empty():
            try:
                try:
                    # Use a shorter timeout to allow periodic commits even if queue is empty
                    work, success, result, meta = await asyncio.wait_for(
                        self.completed_queue.get(),
                        timeout=0.5,
                    )
                except TimeoutError:
                    # Check if we need to commit
                    if pending_count > 0 and time.time() - last_commit > commit_interval:
                        try:
                            self.db.conn.commit()
                            pending_count = 0
                            last_commit = time.time()
                        except Exception as e:
                            print(f"❌ Commit failed: {e}")
                    continue
                
                if success and result:
                    # Write to database (sync, fine since we're only writer)
                    try:
                        self._write_enrichment(work, result, meta, commit=False)
                        self._items_completed += 1
                        pending_count += 1
                        
                        # Log success
                        fname = work.slice_view.file_path.name
                        print(f"✓ {fname} L{work.slice_view.start_line}-{work.slice_view.end_line}")
                        
                        # Batch commit
                        if pending_count >= commit_threshold:
                            self.db.conn.commit()
                            pending_count = 0
                            last_commit = time.time()
                        
                    except Exception as e:
                        print(f"❌ Write failed: {e}")
                else:
                    self._items_completed += 1  # Count as processed even if failed
                    
            except asyncio.CancelledError:
                break
        
        # Final commit
        if pending_count > 0:
            try:
                self.db.conn.commit()
            except Exception as e:
                print(f"❌ Final commit failed: {e}")
    
    async def _wait_for_completion(self):
        """Wait until we've completed the target number of items."""
        while self._items_completed < self._target_limit:
            await asyncio.sleep(0.5)
            
            # Log progress periodically
            if self._items_completed > 0 and self._items_completed % 10 == 0:
                in_flight = sum(p.in_flight for p in self.pools)
                print(f"📊 Progress: {self._items_completed}/{self._target_limit} (in-flight: {in_flight})")
    
    def _get_pending_spans(self, limit: int) -> list[dict]:
        """Get pending spans from database."""
        from llmc.rag.workers import enrichment_plan
        return enrichment_plan(self.db, self.repo_root, limit=limit, cooldown_seconds=0)
    
    def _create_work_item(self, span_data: dict) -> WorkItem | None:
        """Create a WorkItem from span data."""
        try:
            file_path = span_data.get("path", "")
            lines = span_data.get("lines", [0, 0])
            
            slice_view = EnrichmentSliceView(
                span_hash=span_data["span_hash"],
                file_path=Path(file_path),
                start_line=lines[0] if lines else 0,
                end_line=lines[1] if len(lines) > 1 else 0,
                content_type=span_data.get("content_type", "code"),
                classifier_confidence=0.8,
                approx_token_count=span_data.get("approx_tokens", 500),
            )
            
            item_dict = {
                "span_hash": span_data["span_hash"],
                "path": file_path,
                "file_path": file_path,
                "lines": lines,
                "line_range": lines,
                "content": span_data.get("content", ""),
                "code_snippet": span_data.get("content", "")[:800],
                "symbol": span_data.get("symbol", ""),
                "kind": span_data.get("kind", ""),
                "content_type": span_data.get("content_type", "code"),
            }
            
            prompt = build_enrichment_prompt(item_dict, self.repo_root)
            
            return WorkItem(
                slice_view=slice_view,
                prompt=prompt,
                item_dict=item_dict,
            )
            
        except Exception as e:
            print(f"❌ Failed to create work item: {e}")
            return None
    
    def _write_enrichment(self, work: WorkItem, result: dict, meta: dict | None, commit: bool = True):
        """Write enrichment result to database."""
        payload = {
            **result,
            "model": meta.get("model", "unknown") if meta else "unknown",
            "schema_version": result.get("schema_version", "enrichment.v1"),
        }
        self.db.store_enrichment(work.slice_view.span_hash, payload, meta=meta or {})
        if commit:
            self.db.conn.commit()


# CLI entry point for testing
async def _test_run():
    """Test the conveyor belt pipeline."""
    import sys
    
    repo_root = Path.cwd()
    if not (repo_root / "llmc.toml").exists():
        print("❌ Run from repo root (no llmc.toml found)")
        sys.exit(1)
    
    print("🏭 Starting Conveyor Belt Pipeline...")
    pipeline = ConveyorBeltPipeline.from_config(repo_root)
    
    print(f"📦 Loaded {len(pipeline.pools)} backend pools:")
    for pool in pipeline.pools:
        print(f"   - {pool.name} (concurrency={pool.concurrency})")
    
    result = await pipeline.run(limit=20, timeout=120.0)
    
    print("\n📊 Results:")
    print(f"   Attempted: {result.attempted}")
    print(f"   Succeeded: {result.succeeded}")
    print(f"   Failed: {result.failed}")
    print(f"   Duration: {result.duration_sec:.1f}s")
    print(f"   Throughput: {result.throughput:.1f} T/s")
    
    print("\n📈 Per-backend stats:")
    for name, stats in result.per_backend_stats.items():
        print(f"   {name}: {stats}")


if __name__ == "__main__":
    asyncio.run(_test_run())
