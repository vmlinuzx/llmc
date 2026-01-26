#!/usr/bin/env python3
"""
Async Parallel Enrichment - Multi-Backend Fan-Out Pattern

Uses Python 3.11+ asyncio.TaskGroup with per-backend semaphores to keep
ALL configured servers busy simultaneously.

Key insight: A single shared semaphore causes all work to go to the fastest
server. Per-backend semaphores ensure each server always has work in flight.
"""

import asyncio
from dataclasses import dataclass, field
from itertools import cycle
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from llmc.rag.database import Database


@dataclass
class AsyncEnrichmentResult:
    """Result of an async enrichment run."""
    attempted: int = 0
    succeeded: int = 0
    failed: int = 0
    duration_sec: float = 0.0
    per_backend: dict[str, int] = field(default_factory=dict)
    
    @property
    def throughput(self) -> float:
        """Estimated tokens per second (350 tokens/span average)."""
        if self.duration_sec <= 0:
            return 0.0
        return (self.succeeded * 350) / self.duration_sec


async def enrich_span_async(
    backend,
    prompt: str,
    item: dict,
    span_hash: str,
    db: "Database",
) -> tuple[bool, dict | None, dict | None, str | None]:
    """Enrich a single span asynchronously.
    
    Returns:
        (success, result_payload, meta, error_message)
    """
    try:
        # Call LLM - run sync backend in executor to not block event loop
        loop = asyncio.get_event_loop()
        result, meta = await loop.run_in_executor(
            None,
            lambda: backend.generate(prompt, item=item)
        )
        
        if result and (result.get("summary_120w") or result.get("summary")):
            return True, result, meta, None
        else:
            return False, None, None, "Empty result from LLM"
            
    except Exception as e:
        return False, None, None, str(e)


async def run_async_enrichment(
    repos: list[str],
    batch_size: int = 50,
    per_backend_concurrency: int = 2,
    timeout: float = 120.0,
) -> AsyncEnrichmentResult:
    """Run async parallel enrichment across all repos with multi-backend fan-out.
    
    Uses per-backend semaphores to keep ALL servers busy simultaneously.
    
    Args:
        repos: List of repo paths to process
        batch_size: Max spans to process per repo
        per_backend_concurrency: Parallel requests PER backend (not total)
        timeout: Max runtime in seconds
        
    Returns:
        AsyncEnrichmentResult with stats
    """
    from llmc.rag.config import index_path_for_write
    from llmc.rag.database import Database
    from llmc.rag.enrichment_factory import create_backend_from_spec
    from llmc.rag.enrichment_pipeline import build_enrichment_prompt
    from llmc.rag.enrichment_router import EnrichmentSliceView, build_router_from_toml
    
    start = time.monotonic()
    result = AsyncEnrichmentResult()
    
    # Collect all work items across repos
    all_work: list[tuple[Database, Path, str, dict, str]] = []  # (db, repo, hash, item, prompt)
    dbs_to_close: list[Database] = []
    all_backend_specs: list[Any] = []  # Available backends from first repo's chain
    
    for repo_path in repos:
        repo = Path(repo_path)
        if not repo.exists():
            continue
            
        try:
            index_path = index_path_for_write(repo)
            db = Database(index_path)
            dbs_to_close.append(db)
            
            # Get pending spans
            pending = db.pending_enrichments(limit=batch_size)
            if not pending:
                continue
            
            # Get router for backend specs (use first repo to get the chain)
            router = build_router_from_toml(repo)
            
            for span_work_item in pending:
                span_hash = span_work_item.span_hash
                
                # Build slice view for routing
                slice_view = EnrichmentSliceView(
                    span_hash=span_hash,
                    file_path=Path(span_work_item.file_path),
                    start_line=span_work_item.start_line,
                    end_line=span_work_item.end_line,
                    content_type=getattr(span_work_item, "slice_type", "code"),
                    classifier_confidence=getattr(span_work_item, "classifier_confidence", 0.8),
                    approx_token_count=500,
                )
                
                # Read source content
                try:
                    content = span_work_item.read_source(repo)
                except Exception:
                    content = ""
                
                # Build prompt
                item = {
                    "span_hash": span_hash,
                    "path": str(span_work_item.file_path),
                    "file_path": str(span_work_item.file_path),
                    "lines": [span_work_item.start_line, span_work_item.end_line],
                    "line_range": [span_work_item.start_line, span_work_item.end_line],
                    "content": content,
                    "code_snippet": content[:800] if content else "",
                    "content_type": getattr(span_work_item, "slice_type", "code"),
                }
                prompt = build_enrichment_prompt(item, repo)
                
                # Get all backend specs for this content type (collect once)
                if not all_backend_specs:
                    decision = router.choose_chain(slice_view)
                    all_backend_specs = decision.backend_specs
                
                all_work.append((db, repo, span_hash, item, prompt))
                
        except Exception as e:
            print(f"❌ {repo.name}: Failed to load: {e}", flush=True)
            continue
    
    if not all_work:
        for db in dbs_to_close:
            try:
                db.close()
            except Exception:
                pass
        return result
    
    if not all_backend_specs:
        print("❌ No backend specs found in chain", flush=True)
        return result
    
    # Limit to top N backends (use fast backends, avoid slow 14b/8b fallbacks)
    max_backends = 2
    working_backends = all_backend_specs[:max_backends]
    
    # Create per-backend semaphores and work queues
    backend_semaphores: dict[str, asyncio.Semaphore] = {}
    backend_adapters: dict[str, Any] = {}  # Reuse adapters
    
    for spec in working_backends:
        name = spec.name or spec.model
        backend_semaphores[name] = asyncio.Semaphore(per_backend_concurrency)
        backend_adapters[name] = create_backend_from_spec(spec)
    
    # Round-robin assign work to backends (ensures even distribution)
    backend_cycle = cycle(working_backends)
    work_with_backend: list[tuple[Database, Path, str, dict, str, Any]] = []
    
    for db, repo, span_hash, item, prompt in all_work:
        backend_spec = next(backend_cycle)
        work_with_backend.append((db, repo, span_hash, item, prompt, backend_spec))
    
    backends_str = ", ".join(s.name or s.model for s in working_backends)
    print(f"🚀 Async enrichment: {len(all_work)} spans → {len(working_backends)} backends [{backends_str}] ({per_backend_concurrency} per backend)", flush=True)
    
    # Queue for serializing DB writes (avoid "database is locked")
    write_queue: asyncio.Queue = asyncio.Queue()
    
    # Process with TaskGroup - each task uses its backend's semaphore
    async def process_span(db: "Database", repo: Path, span_hash: str, item: dict, prompt: str, backend_spec):
        import time as _time
        
        backend_name = backend_spec.name or backend_spec.model
        sem = backend_semaphores[backend_name]
        backend = backend_adapters[backend_name]
        
        async with sem:  # Per-backend concurrency limit
            span_start = _time.monotonic()  # Start timing INSIDE semaphore
            try:
                success, payload, meta, error = await enrich_span_async(backend, prompt, item, span_hash, db)
                
                duration = _time.monotonic() - span_start
                
                if success and payload:
                    # Queue the write instead of doing it here
                    await write_queue.put((db, span_hash, payload, meta))
                    
                    result.succeeded += 1
                    
                    # Informative log line
                    fname = Path(item.get("file_path", "unknown")).name
                    lines = item.get("lines", [0, 0])
                    start_line, end_line = lines[0], lines[1] if len(lines) > 1 else lines[0]
                    
                    model = meta.get("model", backend_spec.model) if meta else backend_spec.model
                    host = meta.get("host", "") if meta else ""
                    if not host and hasattr(backend_spec, "url") and backend_spec.url:
                        from urllib.parse import urlparse
                        parsed = urlparse(backend_spec.url)
                        host = parsed.netloc
                    
                    # Use real T/s from LLM if available, otherwise estimate
                    tps = meta.get("tokens_per_second", 0) if meta else 0
                    if not tps and duration > 0:
                        # Fallback estimate for backends that don't report T/s
                        tps = 350.0 / duration
                    
                    server_note = f" @{host}" if host else ""
                    print(f"✓ {fname} L{start_line}-{end_line} | {model}{server_note} | {duration:.1f}s {tps:.0f}T/s", flush=True)
                    
                    result.per_backend[backend_name] = result.per_backend.get(backend_name, 0) + 1
                else:
                    result.failed += 1
                    duration = _time.monotonic() - span_start
                    fname = Path(item.get("file_path", "unknown")).name
                    if error:
                        print(f"✗ {fname} @{backend_name}: {error[:50]} ({duration:.1f}s)", flush=True)
                        
            except Exception as e:
                result.failed += 1
                print(f"✗ Exception @{backend_name}: {e}", flush=True)
            finally:
                result.attempted += 1
    
    # Writer task - processes DB writes serially to avoid locks
    async def writer_task():
        while True:
            try:
                item = await asyncio.wait_for(write_queue.get(), timeout=0.5)
                if item is None:  # Shutdown signal
                    break
                db, span_hash, payload, meta = item
                try:
                    db.store_enrichment(span_hash, payload, meta=meta)
                except Exception as e:
                    print(f"⚠️ DB write failed: {e}", flush=True)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
    
    try:
        async with asyncio.timeout(timeout):
            # Start writer task
            writer = asyncio.create_task(writer_task())
            
            async with asyncio.TaskGroup() as tg:
                for db, repo, span_hash, item, prompt, backend_spec in work_with_backend:
                    tg.create_task(process_span(db, repo, span_hash, item, prompt, backend_spec))
            
            # Signal writer to stop and wait for it
            await write_queue.put(None)
            await writer
            
    except TimeoutError:
        print(f"⏱️ Timeout after {timeout}s", flush=True)
    except ExceptionGroup as eg:
        print(f"⚠️ {len(eg.exceptions)} errors during enrichment", flush=True)
        for exc in eg.exceptions[:3]:
            print(f"   └─ {type(exc).__name__}: {exc}", flush=True)
    
    # Commit all databases
    for db in dbs_to_close:
        try:
            db.conn.commit()
            db.close()
        except Exception as e:
            print(f"⚠️ DB cleanup error: {e}", flush=True)
    
    result.duration_sec = time.monotonic() - start
    
    # Summary
    if result.attempted > 0:
        print(
            f"✅ Enriched {result.succeeded}/{result.attempted} in {result.duration_sec:.1f}s "
            f"({result.throughput:.0f} T/s)",
            flush=True
        )
        for name, count in sorted(result.per_backend.items()):
            print(f"   └─ {name}: {count}", flush=True)
    
    return result


def run_async_enrichment_sync(
    repos: list[str],
    batch_size: int = 50,
    concurrency: int = 6,
    timeout: float = 120.0,
) -> AsyncEnrichmentResult:
    """Synchronous wrapper for run_async_enrichment.
    
    Note: 'concurrency' is now PER-BACKEND, not total.
    With 3 backends and concurrency=2, you get 6 parallel requests.
    """
    # Convert total concurrency to per-backend (min 1)
    # If user wants 6 total and there are ~3 backends, use 2 per backend
    per_backend = max(1, concurrency // 3)
    return asyncio.run(run_async_enrichment(repos, batch_size, per_backend, timeout))


# CLI for testing
if __name__ == "__main__":
    import sys
    
    repos = sys.argv[1:] if len(sys.argv) > 1 else ["/home/vmlinux/src/llmc"]
    print(f"Testing async enrichment on: {repos}")
    
    result = run_async_enrichment_sync(repos, batch_size=10, concurrency=6, timeout=60)
    print(f"\nResult: {result}")
